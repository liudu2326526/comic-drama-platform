import logging
import asyncio
from time import monotonic
from typing import Any
from sqlalchemy import select
from app.infra import get_volcano_asset_client
from app.infra.db import get_session_factory
from app.infra.apimart_image_client import get_character_image_client, get_character_image_model
from app.infra.volcano_errors import VolcanoContentFilterError, is_content_filter_code
from app.infra.volcano_client import get_volcano_client
from app.infra.asset_store import build_asset_url, persist_generated_asset
from app.domain.models import Character, Job, Project
from app.domain.services.character_service import CharacterService
from app.pipeline.transitions import is_job_canceled, update_job_progress
from app.tasks.async_runner import run_async_task
from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.tasks.ai.prompt_builders import (
    build_character_full_body_prompt,
    build_character_headshot_prompt,
    build_character_turnaround_prompt,
)

logger = logging.getLogger(__name__)


def _extract_image_url(resp: Any) -> str:
    if isinstance(resp, dict):
        return resp["data"][0]["url"]
    return resp.data[0].url


def _extract_video_url(resp: dict[str, Any]) -> str:
    content = resp.get("content") or {}
    video_url = content.get("video_url")
    if not video_url:
        raise RuntimeError("video provider returned no video_url")
    return str(video_url)


def _is_human_character(char: Character) -> bool:
    return bool(char.is_humanoid)


def _asset_uri_from_video_style_ref(video_style_ref: object) -> str | None:
    if not isinstance(video_style_ref, dict):
        return None
    asset_id = str(video_style_ref.get("asset_id") or "").strip()
    asset_status = str(video_style_ref.get("asset_status") or "").strip()
    if asset_id and asset_status == "Active":
        return f"asset://{asset_id}"
    return None


def _provider_error_code(error: object) -> str:
    if isinstance(error, dict):
        for key in ("code", "message"):
            value = str(error.get(key) or "").strip()
            if value:
                return value
        return str(error)
    return str(error or "").strip()


def _is_reference_privacy_failure(exc: Exception) -> bool:
    if isinstance(exc, VolcanoContentFilterError):
        return True
    message = str(exc)
    return any(
        token in message
        for token in (
            "InputImageSensitiveContentDetected",
            "InputSensitiveContentDetected",
            "ContentFilter",
            "content_filter",
            "隐私",
            "敏感",
        )
    )


def _raise_provider_terminal_error(provider: dict[str, Any], status: object) -> None:
    code = _provider_error_code(provider.get("error"))
    if is_content_filter_code(code):
        raise VolcanoContentFilterError(code)
    raise RuntimeError(provider.get("error") or f"video provider status: {status}")


async def _generate_turnaround_video(
    *,
    project: Project,
    prompt: str,
    image_inputs: list[dict[str, str]],
    job_id: str,
    session,
) -> str:
    settings = get_settings()
    client = get_volcano_client()
    task = await client.video_generations_create(
        model=settings.ark_video_model_standard,
        prompt=prompt,
        image_inputs=image_inputs,
        duration=8,
        resolution=settings.ark_video_default_resolution,
        ratio="9:16",
        generate_audio=True,
        watermark=settings.ark_video_watermark,
        return_last_frame=settings.ark_video_return_last_frame,
        execution_expires_after=settings.ark_video_execution_expires_after,
    )
    task_id = task.get("id")
    if not task_id:
        raise RuntimeError("video provider returned no task id")

    deadline = monotonic() + settings.ark_video_execution_expires_after
    attempt = 0
    provider: dict[str, Any] | None = None
    while monotonic() < deadline:
        if await is_job_canceled(session, job_id):
            return ""
        attempt += 1
        provider = await client.video_generations_get(task_id)
        status = provider.get("status")
        if status == "succeeded":
            return await persist_generated_asset(
                url=_extract_video_url(provider),
                project_id=project.id,
                kind="character_turnaround",
                ext="mp4",
            )
        if status in {"failed", "expired", "cancelled", "canceled"}:
            _raise_provider_terminal_error(provider, status)
        await update_job_progress(session, job_id, done=min(80 + attempt, 95), total=100, status="running")
        await session.commit()
        await asyncio.sleep(5)

    raise RuntimeError("character turnaround video generation timed out")


async def _ensure_character_asset_uri_for_turnaround(session, char: Character, job_id: str) -> str:
    if not char.reference_image_url and char.full_body_image_url:
        char.reference_image_url = char.full_body_image_url
        await session.flush()

    async def on_step(step: int, _label: str) -> None:
        await update_job_progress(session, job_id, progress=min(82 + step * 3, 91), status="running")
        await session.commit()

    await CharacterService._register_asset_steps(session, char, on_step=on_step)
    await session.flush()
    asset_uri = _asset_uri_from_video_style_ref(char.video_style_ref)
    if not asset_uri:
        raise RuntimeError("参考图入人像库失败，无法重试 360 角色展示视频")
    return asset_uri


async def _ensure_headshot_asset_uri_for_turnaround(session, char: Character, job_id: str) -> str:
    video_ref = dict(char.video_style_ref or {})
    asset_id = str(video_ref.get("turnaround_headshot_asset_id") or "").strip()
    asset_status = str(video_ref.get("turnaround_headshot_asset_status") or "").strip()
    if asset_id and asset_status == "Active":
        return f"asset://{asset_id}"

    group_id = str(video_ref.get("asset_group_id") or "").strip()
    if not group_id:
        raise RuntimeError("参考图入人像库失败，缺少 AssetGroup")

    headshot_url = build_asset_url(char.headshot_image_url)
    if not headshot_url:
        raise RuntimeError("头像参考图 URL 组装失败，无法入人像库")

    asset_client = get_volcano_asset_client()
    try:
        await update_job_progress(session, job_id, progress=92, status="running")
        await session.commit()
        asset = await asset_client.create_asset(
            group_id=group_id,
            url=headshot_url,
            name=f"{char.name}_headshot",
        )
        video_ref = {
            **video_ref,
            "turnaround_headshot_asset_id": asset["Id"],
            "turnaround_headshot_asset_status": "Pending",
        }
        char.video_style_ref = dict(video_ref)
        await session.flush()
        await session.commit()

        await update_job_progress(session, job_id, progress=94, status="running")
        await session.commit()
        final = await asset_client.wait_asset_active(asset["Id"], timeout=180)
        video_ref = {
            **video_ref,
            "turnaround_headshot_asset_status": final["Status"],
        }
        char.video_style_ref = dict(video_ref)
        await session.flush()
        return f"asset://{asset['Id']}"
    finally:
        close = getattr(asset_client, "aclose", None)
        if close is not None:
            await close()


async def _ensure_turnaround_asset_uris(session, char: Character, job_id: str) -> tuple[str, str]:
    full_body_asset_uri = await _ensure_character_asset_uri_for_turnaround(session, char, job_id)
    headshot_asset_uri = await _ensure_headshot_asset_uri_for_turnaround(session, char, job_id)
    return full_body_asset_uri, headshot_asset_uri


async def _update_parent_progress(session, job_id: str, *, failure_msg: str | None = None) -> None:
    job = await session.get(Job, job_id)
    parent_id = job.parent_id if job else None
    if not parent_id:
        return

    from sqlalchemy import func, select

    terminal_stmt = select(func.count(Job.id)).where(
        Job.parent_id == parent_id,
        Job.status.in_(["succeeded", "failed", "canceled"]),
    )
    failed_stmt = select(func.count(Job.id)).where(
        Job.parent_id == parent_id,
        Job.status.in_(["failed", "canceled"]),
    )
    done_count = (await session.execute(terminal_stmt)).scalar() or 0
    failed_count = (await session.execute(failed_stmt)).scalar() or 0
    parent_job = await session.get(Job, parent_id)
    if parent_job:
        await update_job_progress(session, parent_id, done=done_count)
        if failed_count:
            if parent_job.status in {"queued", "running"}:
                await update_job_progress(
                    session,
                    parent_id,
                    status="failed",
                    error_msg=failure_msg or "部分角色资产生成失败",
                )
        elif done_count >= (parent_job.total or 0):
            await update_job_progress(session, parent_id, status="succeeded", progress=100)


async def run_character_asset_generation(
    character_id: str,
    job_id: str,
    *,
    session=None,
    replace_existing: bool = False,
) -> None:
    if session is not None:
        await _run_character_asset_generation(session, character_id, job_id, replace_existing=replace_existing)
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _run_character_asset_generation(session, character_id, job_id, replace_existing=replace_existing)


async def _run_character_asset_generation(
    session,
    character_id: str,
    job_id: str,
    *,
    replace_existing: bool = False,
) -> None:
    try:
        if await is_job_canceled(session, job_id):
            return
        await update_job_progress(session, job_id, status="running", progress=10)
        await session.commit()

        char = await session.get(Character, character_id)
        if not char:
            logger.error("Character %s not found", character_id)
            await update_job_progress(session, job_id, status="failed", error_msg="Character not found")
            await session.commit()
            return

        project = await session.get(Project, char.project_id)
        if not project:
            logger.error("Project %s not found", char.project_id)
            await update_job_progress(session, job_id, status="failed", error_msg="Project not found")
            await session.commit()
            return
        character_names = list(
            (
                await session.execute(
                    select(Character.name).where(Character.project_id == char.project_id)
                )
            ).scalars()
        )

        client = get_character_image_client()
        image_model = get_character_image_model()
        style_ref = build_asset_url(project.character_style_reference_image_url)
        style_refs = [style_ref] if style_ref else None

        if replace_existing or not char.full_body_image_url:
            full_body_resp = await client.image_generations(
                model=image_model,
                prompt=build_character_full_body_prompt(project, char, has_reference_image=bool(style_refs)),
                references=style_refs,
                n=1,
                size="1024x1024",
            )
            if await is_job_canceled(session, job_id):
                return
            full_body_key = await persist_generated_asset(
                url=_extract_image_url(full_body_resp),
                project_id=char.project_id,
                kind="character_full_body",
                ext="png",
            )
            char.full_body_image_url = full_body_key
            char.reference_image_url = full_body_key
        else:
            full_body_key = char.full_body_image_url
            char.reference_image_url = char.reference_image_url or full_body_key

        await update_job_progress(session, job_id, progress=55)
        await session.commit()

        if await is_job_canceled(session, job_id):
            return
        full_body_url = build_asset_url(full_body_key) if full_body_key else None
        headshot_refs = [url for url in [full_body_url] if url]
        headshot_resp = await client.image_generations(
            model=image_model,
            prompt=build_character_headshot_prompt(project, char, has_reference_image=bool(headshot_refs)),
            references=headshot_refs or None,
            n=1,
            size="1024x1024",
        )
        if await is_job_canceled(session, job_id):
            return
        headshot_key = await persist_generated_asset(
            url=_extract_image_url(headshot_resp),
            project_id=char.project_id,
            kind="character_headshot",
            ext="png",
        )
        char.headshot_image_url = headshot_key

        if _is_human_character(char):
            await update_job_progress(session, job_id, progress=80)
            await session.commit()
            if await is_job_canceled(session, job_id):
                return
            full_body_url = build_asset_url(char.full_body_image_url)
            headshot_url = build_asset_url(char.headshot_image_url)
            if not full_body_url or not headshot_url:
                raise RuntimeError("生成 360 参考视频需要先完成全身参考图和头像参考图")
            turnaround_prompt = build_character_turnaround_prompt(
                project,
                char,
                character_names=character_names,
                has_reference_image=True,
            )
            public_image_inputs = [
                {"role": "first_frame", "url": full_body_url},
                {"role": "last_frame", "url": headshot_url},
            ]
            try:
                turnaround_key = await _generate_turnaround_video(
                    project=project,
                    prompt=turnaround_prompt,
                    image_inputs=public_image_inputs,
                    job_id=job_id,
                    session=session,
                )
            except Exception as exc:
                if not _is_reference_privacy_failure(exc):
                    raise
                logger.info(
                    "Retry character turnaround video with asset library reference after provider rejection: %s",
                    exc,
                )
                if await is_job_canceled(session, job_id):
                    return
                full_body_asset_uri, headshot_asset_uri = await _ensure_turnaround_asset_uris(session, char, job_id)
                if await is_job_canceled(session, job_id):
                    return
                turnaround_key = await _generate_turnaround_video(
                    project=project,
                    prompt=turnaround_prompt,
                    image_inputs=[
                        {"role": "first_frame", "url": full_body_asset_uri},
                        {"role": "last_frame", "url": headshot_asset_uri},
                    ],
                    job_id=job_id,
                    session=session,
                )
            if await is_job_canceled(session, job_id):
                return
            if not turnaround_key:
                return
            char.turnaround_image_url = turnaround_key
            char.voice_profile = {
                "enabled": True,
                "description": f"{char.name} 的角色声音待配置",
                "source": "placeholder",
            }

        await session.commit()
        await update_job_progress(session, job_id, status="succeeded", progress=100)
        await session.commit()
        await _update_parent_progress(session, job_id)
        await session.commit()
        logger.info("Character %s dual assets generated: %s, %s", character_id, full_body_key, headshot_key)
    except Exception as e:
        if await is_job_canceled(session, job_id):
            await session.rollback()
            return
        logger.exception("Error in gen_character_asset_task: %s", e)
        error_msg = str(e) or type(e).__name__
        await update_job_progress(session, job_id, status="failed", error_msg=error_msg)
        await session.commit()
        await _update_parent_progress(session, job_id, failure_msg=error_msg)
        await session.commit()

@celery_app.task(name="ai.gen_character_asset", queue="ai", bind=True)
def gen_character_asset(self, character_id: str, job_id: str, replace_existing: bool = False):
    run_async_task(run_character_asset_generation(character_id, job_id, replace_existing=replace_existing))
