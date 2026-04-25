import logging

from sqlalchemy import select

from app.config import get_settings
from app.domain.models import Character, Job, Project
from app.infra import get_volcano_client
from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.tasks.ai.gen_character_asset import gen_character_asset
from app.tasks.async_runner import dispatch_task_group, run_async_task
from app.tasks.celery_app import celery_app
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)
VALID_ROLE_TYPES = {"supporting", "atmosphere"}


def _normalize_character_rows(payload: object) -> list[dict[str, str | None]]:
    if isinstance(payload, dict):
        raw_rows = payload.get("characters", [])
    elif isinstance(payload, list):
        raw_rows = payload
    else:
        raw_rows = []

    normalized: list[dict[str, str | None]] = []
    seen_names: set[str] = set()
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        role_type = str(item.get("role_type", "supporting")).strip() or "supporting"
        if role_type == "protagonist":
            role_type = "supporting"
        if role_type not in VALID_ROLE_TYPES:
            role_type = "supporting"
        summary = item.get("summary")
        description = item.get("description")
        normalized.append(
            {
                "name": name,
                "role_type": role_type,
                "summary": str(summary).strip() if summary else None,
                "description": str(description).strip() if description else None,
            }
        )
    return normalized


async def _upsert_character(
    session,
    *,
    project_id: str,
    row: dict[str, str | None],
) -> Character:
    stmt = select(Character).where(
        Character.project_id == project_id,
        Character.name == row["name"],
    )
    character = (await session.execute(stmt)).scalar_one_or_none()
    if character is None:
        character = Character(project_id=project_id, name=row["name"] or "")
        session.add(character)

    character.role_type = row["role_type"] or "supporting"
    character.is_protagonist = False
    character.summary = row["summary"]
    character.description = row["description"]
    await session.flush()
    return character


async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    settings = get_settings()

    async with session_factory() as session:
        next_job: Job | None = None
        try:
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
                "请根据以下小说内容提取其中的主要角色、关键配角和氛围配角。\n\n"
                f"小说内容：\n{project.story or ''}\n\n"
                "请以 JSON 数组格式返回，每个对象包含："
                "name, role_type(protagonist/supporting/atmosphere), summary, description。"
            )
            client = get_volcano_client()
            response = await client.chat_completions(
                model=settings.ark_chat_model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            rows = _normalize_character_rows(extract_json(content))
            if not rows:
                await update_job_progress(session, job_id, status="failed", error_msg="未识别到角色")
                await session.commit()
                return

            await update_job_progress(session, job_id, progress=55)

            characters: list[Character] = []
            for row in rows:
                characters.append(await _upsert_character(session, project_id=project_id, row=row))

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
                await dispatch_task_group(
                    gen_character_asset,
                    [
                        (character_id, child_job.id)
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
