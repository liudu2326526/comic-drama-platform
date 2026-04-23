import asyncio
import json
import logging

from app.domain.models import Job
from app.config import get_settings
from app.domain.services import ShotDraftService
from app.domain.services.reference_candidates import (
    default_selected_references,
    selected_references_from_ids,
)
from app.infra import get_volcano_client
from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.tasks.celery_app import celery_app
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


def _build_selection_messages(context: dict) -> list[dict[str, str]]:
    shot = context["shot"]
    references = context["reference_candidates"]
    references_json = json.dumps(references, ensure_ascii=False, indent=2)
    system = (
        "你是内部镜头参考图选择助手。请先从候选参考图中选出当前镜头真正需要的场景和人物参考。"
        "你必须直接给出一个 JSON 对象，键只允许为 reference_ids, selection_notes。"
        "reference_ids 必须从候选参考图的 id 中选择，可返回空数组。"
        "最多选择 1 张 scene 和 2 张 character，不要为了凑数硬选。"
        "如果镜头文案没有明确人物，可以只选场景。"
    )
    user = (
        "请先为当前镜头选择参考图。\n"
        f"项目：{json.dumps(context['project'], ensure_ascii=False)}\n"
        f"镜头：{json.dumps(shot, ensure_ascii=False)}\n"
        f"候选参考图：\n{references_json}\n\n"
        "返回 JSON 格式：\n"
        "{\n"
        '  "reference_ids": ["scene:xxx", "character:xxx"],\n'
        '  "selection_notes": {\n'
        '    "scene": "为什么选这个场景",\n'
        '    "characters": ["为什么选这些人物"]\n'
        "  }\n"
        "}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_prompt_messages(context: dict, selected_references: list[dict]) -> list[dict[str, str]]:
    shot = context["shot"]
    skill_prompt = context["skill_prompt"]
    references_json = json.dumps(selected_references, ensure_ascii=False, indent=2)
    system = (
        "你是内部镜头草稿生成助手。请参考下述 Seedance 提示词优化规范进行重写，但不要输出面向用户的讲解。"
        "你必须直接给出一个 JSON 对象，键只允许为 prompt, optimizer_notes。"
        "prompt 必须是中文，可直接用于后续视频生成，不要输出 markdown。"
        "你只能基于已选中的参考图生成 prompt，不得引用未选中的参考图。"
        "如果信息不足，请保守补全并把假设写入 optimizer_notes.assumptions。"
        f"\n\n以下是提示词优化规范：\n{skill_prompt}"
    )
    user = (
        "请基于当前镜头与已选参考图，生成一份可直接用于视频生成的草稿提示词。\n"
        f"项目：{json.dumps(context['project'], ensure_ascii=False)}\n"
        f"镜头：{json.dumps(shot, ensure_ascii=False)}\n"
        f"已选参考图：\n{references_json}\n\n"
        "返回 JSON 格式：\n"
        "{\n"
        '  "prompt": "最终提示词",\n'
        '  "optimizer_notes": {\n'
        '    "issues": ["..."],\n'
        '    "principles": ["..."],\n'
        '    "assumptions": ["..."]\n'
        "  }\n"
        "}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _normalize_selection_payload(payload: object, candidates: list[dict]) -> tuple[list[dict], dict | None]:
    if not isinstance(payload, dict):
        raise ValueError("参考图选择结果格式错误")

    selected = selected_references_from_ids(candidates, payload.get("reference_ids", []))
    if not selected:
        selected = default_selected_references(candidates)

    selection_notes = payload.get("selection_notes")
    if selection_notes is not None and not isinstance(selection_notes, dict):
        selection_notes = {"notes": selection_notes}
    return selected, selection_notes


def _normalize_prompt_payload(payload: object) -> tuple[str, dict | None]:
    if not isinstance(payload, dict):
        raise ValueError("草稿生成结果格式错误")

    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("草稿生成结果缺少 prompt")

    optimizer_notes = payload.get("optimizer_notes")
    if optimizer_notes is not None and not isinstance(optimizer_notes, dict):
        optimizer_notes = {"notes": optimizer_notes}
    return prompt, optimizer_notes


async def _gen_shot_draft_task(project_id: str, shot_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    settings = get_settings()
    async with session_factory() as session:
        try:
            await update_job_progress(session, job_id, status="running", progress=10, done=1, total=5)
            await session.commit()

            service = ShotDraftService(session)
            await service.ensure_draft_renderable(project_id, shot_id)
            context = await service.build_generation_context(project_id, shot_id)
            await update_job_progress(session, job_id, progress=25, done=2, total=5)
            await session.commit()

            client = get_volcano_client()
            selection_response = await client.chat_completions(
                model=settings.ark_chat_model,
                messages=_build_selection_messages(context),
            )
            selection_payload = extract_json(selection_response.choices[0].message.content)
            references, selection_notes = _normalize_selection_payload(
                selection_payload,
                context["reference_candidates"],
            )
            await update_job_progress(session, job_id, progress=50, done=3, total=5)
            await session.commit()

            prompt_response = await client.chat_completions(
                model=settings.ark_chat_model,
                messages=_build_prompt_messages(context, references),
            )
            prompt_payload = extract_json(prompt_response.choices[0].message.content)
            prompt, optimizer_notes = _normalize_prompt_payload(prompt_payload)
            await update_job_progress(session, job_id, progress=75, done=4, total=5)
            await session.commit()

            draft = await service.create_draft(
                shot_id=shot_id,
                prompt=prompt,
                references=references,
                optimizer_snapshot=optimizer_notes,
                source_snapshot={
                    **context,
                    "selected_references": references,
                    "selection_notes": selection_notes,
                },
            )
            actual_job = await session.get(Job, job_id)
            if actual_job is not None:
                actual_job.result = {
                    "shot_id": shot_id,
                    "draft_id": draft.id,
                    "version_no": draft.version_no,
                }
            await update_job_progress(
                session,
                job_id,
                status="succeeded",
                progress=100,
                done=5,
                total=5,
            )
            await session.commit()
        except Exception as exc:
            logger.exception("gen_shot_draft task failed for shot %s", shot_id)
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()


@celery_app.task(name="ai.gen_shot_draft", queue="ai")
def gen_shot_draft(project_id: str, shot_id: str, job_id: str) -> None:
    asyncio.run(_gen_shot_draft_task(project_id, shot_id, job_id))
