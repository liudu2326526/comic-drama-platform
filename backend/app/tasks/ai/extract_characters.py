import logging

from sqlalchemy import select

from app.config import get_settings
from app.domain.models import Character, Job, Project
from app.domain.models.character import CHARACTER_ROLE_VALUES, CHARACTER_VISUAL_TYPE_VALUES
from app.infra import get_volcano_client
from app.infra.db import get_session_factory
from app.pipeline.transitions import is_job_canceled, update_job_progress
from app.tasks.ai.gen_character_asset import gen_character_asset
from app.tasks.async_runner import dispatch_task_group, run_async_task
from app.tasks.celery_app import celery_app
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)
VALID_ROLE_TYPES = set(CHARACTER_ROLE_VALUES)
VALID_VISUAL_TYPES = set(CHARACTER_VISUAL_TYPE_VALUES)
LEGACY_ROLE_ALIASES = {"protagonist": "lead"}
HUMANOID_VISUAL_TYPES = {"human_actor", "stylized_human", "humanoid_monster"}


def _normalize_role_type(value: object) -> str:
    raw = str(value or "supporting").strip() or "supporting"
    raw = LEGACY_ROLE_ALIASES.get(raw, raw)
    return raw if raw in VALID_ROLE_TYPES else "supporting"


def _normalize_visual_type(value: object, *, role_type: str) -> str:
    raw = str(value or "").strip()
    if raw in VALID_VISUAL_TYPES:
        return raw
    if role_type == "crowd":
        return "crowd_group"
    if role_type == "system":
        return "object_entity"
    if role_type == "atmosphere":
        return "anomaly_entity"
    return "human_actor"


def _derive_is_humanoid(visual_type: str) -> bool:
    return visual_type in HUMANOID_VISUAL_TYPES


def _normalize_character_rows(payload: object) -> list[dict[str, str | bool | None]]:
    if isinstance(payload, dict):
        raw_rows = payload.get("characters", [])
    elif isinstance(payload, list):
        raw_rows = payload
    else:
        raw_rows = []

    normalized: list[dict[str, str | bool | None]] = []
    seen_names: set[str] = set()
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        role_type = _normalize_role_type(item.get("role_type"))
        visual_type = _normalize_visual_type(item.get("visual_type"), role_type=role_type)
        is_humanoid = _derive_is_humanoid(visual_type)
        summary = item.get("summary")
        description = item.get("description")
        normalized.append(
            {
                "name": name,
                "role_type": role_type,
                "visual_type": visual_type,
                "is_humanoid": is_humanoid,
                "summary": str(summary).strip() if summary else None,
                "description": str(description).strip() if description else None,
            }
        )
    return normalized


async def _upsert_character(
    session,
    *,
    project_id: str,
    row: dict[str, str | bool | None],
) -> tuple[Character, bool]:
    stmt = select(Character).where(
        Character.project_id == project_id,
        Character.name == row["name"],
    )
    character = (await session.execute(stmt)).scalar_one_or_none()
    created = character is None
    if character is None:
        character = Character(project_id=project_id, name=row["name"] or "")
        session.add(character)

    character.role_type = row["role_type"] or "supporting"
    character.visual_type = row["visual_type"] or "human_actor"
    character.is_humanoid = bool(row.get("is_humanoid", True))
    character.is_protagonist = False
    character.summary = row["summary"]
    character.description = row["description"]
    await session.flush()
    return character, created


async def _cancel_derived_character_asset_work(
    session,
    *,
    next_job: Job,
    created_character_ids: list[str],
) -> None:
    child_jobs = (
        await session.execute(select(Job).where(Job.parent_id == next_job.id))
    ).scalars().all()
    for child_job in child_jobs:
        if child_job.status in {"queued", "running"}:
            await update_job_progress(session, child_job.id, status="canceled")

    if next_job.status in {"queued", "running"}:
        await update_job_progress(session, next_job.id, status="canceled")

    if created_character_ids:
        characters = (
            await session.execute(
                select(Character).where(
                    Character.id.in_(created_character_ids),
                    Character.locked.is_(False),
                )
            )
        ).scalars().all()
        for character in characters:
            await session.delete(character)


async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    settings = get_settings()

    async with session_factory() as session:
        next_job: Job | None = None
        try:
            if await is_job_canceled(session, job_id):
                return
            job = await session.get(Job, job_id)
            if job is None:
                logger.warning("extract_characters job %s not found", job_id)
                return

            await update_job_progress(session, job_id, status="running", progress=10)
            await session.commit()

            project = await session.get(Project, project_id)
            if project is None:
                await update_job_progress(session, job_id, status="failed", error_msg="项目不存在")
                await session.commit()
                return

            prompt = (
                "请根据以下小说内容提取其中的主要角色、关键配角、反派、系统型存在、群体角色和氛围/异常存在。\n\n"
                f"小说内容：\n{project.story or ''}\n\n"
                "请以 JSON 数组格式返回，每个对象包含："
                "name, role_type(lead/supporting/antagonist/atmosphere/crowd/system), "
                "visual_type(human_actor/stylized_human/humanoid_monster/creature/anomaly_entity/object_entity/crowd_group/environment_force), "
                "is_humanoid(boolean), summary, description。\n"
                "role_type 只表示剧情功能；visual_type 决定后续如何生成角色形象。"
                "不得因为角色是反派就把 visual_type 写成怪物，必须依据视觉形态判断。\n"
                "summary 用一句话概括角色在故事中的身份/功能；description 必须只写视觉设定，不写剧情地点、剧情动作、世界观解释或环境背景。\n"
                "description 必须按 visual_type 使用以下字段逐项填写具体值，不能只写字段名或要求。\n"
                "人类/风格化人类字段：年龄段；性别气质；体型轮廓；脸部气质；发型发色；服装层次；主色/辅色；鞋履/配件；唯一辨识点。\n"
                "类人怪物字段：整体轮廓；头部/面部结构；身体结构；材质质感；主色/辅色；肢体/运动方式；威胁特征；唯一辨识点。\n"
                "非人生命体字段：整体轮廓；身体结构；材质质感；主色/辅色；运动方式；攻击/交互特征；尺度感；唯一辨识点。\n"
                "异常体/能量体字段：形态边界；材质/粒子质感；颜色光效；核心符号；变化规律；空间影响；危险感；唯一辨识点。\n"
                "物体/系统载体字段：主体结构；材质工艺；交互界面；发光区域；状态变化；尺度/摆放方式；唯一辨识点。\n"
                "群体角色字段：群体构成；整体服装/形态；颜色倾向；数量密度；行动姿态；与场景关系；唯一辨识点。\n"
                "环境力量字段：空间形态；影响范围；材质/气象质感；颜色光效；动态变化；对环境的破坏方式；唯一辨识点。\n"
                "每个角色的发型、服装配色、体型、配件和唯一辨识点不得与其他角色重复。\n"
            )
            client = get_volcano_client()
            response = await client.chat_completions(
                model=settings.ark_chat_model,
                messages=[{"role": "user", "content": prompt}],
            )
            if await is_job_canceled(session, job_id):
                return
            content = response.choices[0].message.content
            rows = _normalize_character_rows(extract_json(content))
            if not rows:
                await update_job_progress(session, job_id, status="failed", error_msg="未识别到角色")
                await session.commit()
                return

            await update_job_progress(session, job_id, progress=55)

            incoming_names = {str(row["name"]) for row in rows if row.get("name")}
            stale_stmt = select(Character).where(
                Character.project_id == project_id,
                Character.locked.is_(False),
                Character.name.not_in(incoming_names),
            )
            stale_characters = (await session.execute(stale_stmt)).scalars().all()
            for character in stale_characters:
                await session.delete(character)

            characters: list[Character] = []
            created_character_ids: list[str] = []
            for row in rows:
                character, created = await _upsert_character(
                    session,
                    project_id=project_id,
                    row=row,
                )
                characters.append(character)
                if created:
                    created_character_ids.append(character.id)

            character_ids = [character.id for character in characters]
            next_job = Job(
                project_id=project_id,
                kind="gen_character_asset",
                status="running",
                progress=0,
                done=0,
                total=len(character_ids),
                payload={"character_ids": character_ids},
            )
            session.add(next_job)
            await session.flush()

            child_jobs: list[Job] = []
            for character_id in character_ids:
                child_job = Job(
                    project_id=project_id,
                    parent_id=next_job.id,
                    kind="gen_character_asset_single",
                    status="queued",
                    progress=0,
                    done=0,
                    total=None,
                    target_type="character",
                    target_id=character_id,
                )
                session.add(child_job)
                await session.flush()
                child_jobs.append(child_job)

            job.result = {
                "next_job_id": next_job.id,
                "next_kind": "gen_character_asset",
                "character_ids": character_ids,
            }
            await session.commit()

            try:
                if await is_job_canceled(session, job_id):
                    await _cancel_derived_character_asset_work(
                        session,
                        next_job=next_job,
                        created_character_ids=created_character_ids,
                    )
                    await session.commit()
                    return
                await dispatch_task_group(
                    gen_character_asset,
                    [
                        (character_id, child_job.id, True)
                        for character_id, child_job in zip(character_ids, child_jobs, strict=False)
                    ],
                )
            except Exception as exc:
                error_msg = f"dispatch failed: {exc}"
                await update_job_progress(session, next_job.id, status="failed", error_msg=error_msg)
                await update_job_progress(session, job_id, status="failed", error_msg=error_msg)
                await session.commit()
                return

            await update_job_progress(session, job_id, status="succeeded", progress=100)
            await session.commit()
        except Exception as exc:
            if await is_job_canceled(session, job_id):
                await session.rollback()
                return
            logger.exception("extract_characters task failed for job %s", job_id)
            error_msg = str(exc)
            try:
                job = await session.get(Job, job_id)
                if next_job is not None:
                    await session.refresh(next_job)
                    if next_job.status in {"queued", "running"}:
                        await update_job_progress(
                            session,
                            next_job.id,
                            status="failed",
                            error_msg=error_msg,
                        )
                if job is not None and job.status in {"queued", "running"}:
                    await update_job_progress(session, job_id, status="failed", error_msg=error_msg)
                await session.commit()
            except Exception:
                logger.exception("extract_characters failed to persist terminal state for job %s", job_id)


@celery_app.task(name="ai.extract_characters", queue="ai", bind=True)
def extract_characters(self, project_id: str, job_id: str) -> None:
    run_async_task(_run(project_id, job_id))
