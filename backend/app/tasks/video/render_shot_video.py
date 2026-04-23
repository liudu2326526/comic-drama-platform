import asyncio
import logging
from time import monotonic

from app.config import get_settings
from app.domain.models import Character, Job, Scene, ShotVideoRender, StoryboardShot
from app.infra.asset_store import persist_generated_asset
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.infra.volcano_errors import (
    VolcanoContentFilterError,
    VolcanoError,
    VolcanoRateLimitError,
    VolcanoServerError,
    VolcanoTimeoutError,
    humanize_volcano_error_message,
)
from app.pipeline.transitions import (
    mark_shot_video_failed,
    mark_shot_video_running,
    mark_shot_video_succeeded,
    update_job_progress,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _volcano_error_code(exc: VolcanoError) -> str:
    if isinstance(exc, VolcanoContentFilterError):
        return "content_filter"
    if isinstance(exc, VolcanoRateLimitError):
        return "rate_limit"
    if isinstance(exc, VolcanoTimeoutError):
        return "timeout"
    if isinstance(exc, VolcanoServerError):
        return "server_error"
    return "volcano_error"


def _asset_uri_from_video_style_ref(video_style_ref: object) -> str | None:
    if not isinstance(video_style_ref, dict):
        return None
    asset_id = str(video_style_ref.get("asset_id") or "").strip()
    asset_status = str(video_style_ref.get("asset_status") or "").strip()
    if asset_id and asset_status == "Active":
        return f"asset://{asset_id}"
    return None


async def _resolve_reference_for_provider(
    shot: StoryboardShot,
    session,
    item: object,
) -> str | None:
    if not isinstance(item, dict):
        return None

    provider_image_url = str(item.get("provider_image_url") or "").strip()
    if provider_image_url:
        return provider_image_url

    image_url = str(item.get("image_url") or "").strip()
    if not image_url:
        return None
    if image_url.startswith("asset://"):
        return image_url

    source_id = str(item.get("source_id") or "").strip()
    kind = str(item.get("kind") or "").strip()
    if not source_id:
        return image_url

    if kind == "character":
        character = await session.get(Character, source_id)
        if character is not None and character.project_id == shot.project_id:
            return _asset_uri_from_video_style_ref(character.video_style_ref) or image_url

    if kind == "scene":
        scene = await session.get(Scene, source_id)
        if scene is not None and scene.project_id == shot.project_id:
            return _asset_uri_from_video_style_ref(scene.video_style_ref) or image_url

    return image_url


async def _render_shot_video_task(shot_id: str, video_render_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        video = await session.get(ShotVideoRender, video_render_id)
        shot = await session.get(StoryboardShot, shot_id)
        if video is None or shot is None or video.shot_id != shot.id:
            job = await session.get(Job, job_id)
            if job is not None:
                await update_job_progress(session, job_id, status="failed", error_msg="shot/video 不存在")
                await session.commit()
            return

        if video.status == "succeeded":
            job = await session.get(Job, job_id)
            if job is not None and job.status in {"queued", "running"}:
                await update_job_progress(session, job_id, status="succeeded", progress=100)
                job.result = {
                    "shot_id": shot.id,
                    "video_render_id": video.id,
                    "video_url": video.video_url,
                    "last_frame_url": video.last_frame_url,
                }
                await session.commit()
            return

        if video.status == "failed":
            job = await session.get(Job, job_id)
            if job is not None and job.status in {"queued", "running"}:
                await update_job_progress(session, job_id, status="failed", error_msg=video.error_msg or "video render failed")
                await session.commit()
            return

        if video.status == "running":
            job = await session.get(Job, job_id)
            if job is not None and job.status == "queued":
                await update_job_progress(session, job_id, status="running", progress=max(job.progress, 5))
                await session.commit()
            return

        try:
            settings = get_settings()
            client = get_volcano_client()
            snapshot = video.prompt_snapshot or {}
            params = video.params_snapshot or {}
            references = []
            for item in snapshot.get("references", []):
                resolved = await _resolve_reference_for_provider(shot, session, item)
                if resolved:
                    references.append(resolved)

            await update_job_progress(session, job_id, status="running", progress=5)
            mark_shot_video_running(video)
            await session.commit()

            provider_task = await client.video_generations_create(
                model=params.get("model") or params.get("resolved_model") or settings.ark_video_model_fast,
                prompt=snapshot.get("prompt", ""),
                references=references,
                duration=int(params["duration"]) if params.get("duration") is not None else None,
                resolution=str(params.get("resolution", settings.ark_video_default_resolution)),
                ratio=str(params.get("ratio", "adaptive")),
                generate_audio=bool(params.get("generate_audio", settings.ark_video_generate_audio)),
                watermark=bool(params.get("watermark", settings.ark_video_watermark)),
                return_last_frame=bool(params.get("return_last_frame", settings.ark_video_return_last_frame)),
                execution_expires_after=int(params.get("execution_expires_after", settings.ark_video_execution_expires_after)),
            )
            video.provider_task_id = provider_task["id"]
            video.provider_status = "queued"
            await session.commit()

            deadline = monotonic() + settings.ark_video_execution_expires_after
            attempt = 0
            provider = None
            while monotonic() < deadline:
                attempt += 1
                provider = await client.video_generations_get(video.provider_task_id)
                video.provider_status = provider.get("status")
                if provider.get("status") == "succeeded":
                    break
                if provider.get("status") in {"failed", "expired", "cancelled"}:
                    break
                await update_job_progress(session, job_id, done=min(attempt, 95), total=100, status="running")
                await session.commit()
                await asyncio.sleep(5)

            if provider is None:
                raise RuntimeError("video provider returned no status")

            if provider.get("status") == "succeeded":
                content = provider.get("content") or {}
                video_object_key = await persist_generated_asset(
                    url=content["video_url"],
                    project_id=shot.project_id,
                    kind="shot",
                    ext="mp4",
                )
                last_frame_object_key = None
                if content.get("last_frame_url"):
                    last_frame_object_key = await persist_generated_asset(
                        url=content["last_frame_url"],
                        project_id=shot.project_id,
                        kind="shot",
                        ext="png",
                    )
                mark_shot_video_succeeded(
                    shot,
                    video,
                    video_url=video_object_key,
                    last_frame_url=last_frame_object_key,
                )
                job = await update_job_progress(session, job_id, status="succeeded", progress=100)
                job.result = {
                    "shot_id": shot.id,
                    "video_render_id": video.id,
                    "video_url": video_object_key,
                    "last_frame_url": last_frame_object_key,
                }
                await session.commit()
                return

            if provider.get("status") in {"failed", "expired", "cancelled"}:
                msg = provider.get("error") or f"provider status: {provider.get('status')}"
                msg = humanize_volcano_error_message(str(msg))
                mark_shot_video_failed(shot, video, error_code="volcano_error", error_msg=str(msg))
                await update_job_progress(session, job_id, status="failed", error_msg=str(msg))
                await session.commit()
                return

            mark_shot_video_failed(shot, video, error_code="timeout", error_msg="video generation timed out")
            await update_job_progress(session, job_id, status="failed", error_msg="video generation timed out")
            await session.commit()
        except VolcanoError as exc:
            msg = humanize_volcano_error_message(str(exc))
            mark_shot_video_failed(shot, video, error_code=_volcano_error_code(exc), error_msg=msg)
            await update_job_progress(session, job_id, status="failed", error_msg=msg)
            await session.commit()
        except Exception as exc:
            logger.exception("render_shot_video failed")
            mark_shot_video_failed(shot, video, error_code="internal_error", error_msg=str(exc))
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()


@celery_app.task(name="video.render_shot_video", queue="video")
def render_shot_video_task(shot_id: str, video_render_id: str, job_id: str) -> None:
    asyncio.run(_render_shot_video_task(shot_id, video_render_id, job_id))
