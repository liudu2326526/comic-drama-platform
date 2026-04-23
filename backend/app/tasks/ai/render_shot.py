import asyncio
import logging

from app.config import get_settings
from app.domain.models import Job, ShotRender, StoryboardShot
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
    mark_shot_render_failed,
    mark_shot_render_running,
    mark_shot_render_succeeded,
    update_job_progress,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _build_render_prompt(snapshot: dict) -> str:
    shot = snapshot.get("shot") or {}
    scene = snapshot.get("scene") or {}
    characters = snapshot.get("characters") or []
    character_lines = "\n".join(
        f"- {c.get('name')}: {c.get('description')}" for c in characters if c.get("name")
    )
    return (
        "生成一张竖屏漫剧镜头静帧，按文字描述保持角色与场景风格连续。\n"
        f"镜头标题:{shot.get('title', '')}\n"
        f"镜头描述:{shot.get('description', '')}\n"
        f"镜头细节:{shot.get('detail', '')}\n"
        f"场景:{scene.get('name', '')} {scene.get('description', '')}\n"
        f"角色:\n{character_lines}\n"
        "画面要求:电影感构图，清晰主体，适合 9:16 短视频。"
    )


def _extract_image_url(resp: object) -> str:
    if isinstance(resp, dict):
        return resp["data"][0]["url"]
    return resp.data[0].url


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


async def _render_shot_task(shot_id: str, render_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        render = await session.get(ShotRender, render_id)
        shot = await session.get(StoryboardShot, shot_id)
        if render is None or shot is None or render.shot_id != shot.id:
            job = await session.get(Job, job_id)
            if job is not None:
                await update_job_progress(session, job_id, status="failed", error_msg="shot/render 不存在")
                await session.commit()
            return

        if render.status == "succeeded":
            job = await session.get(Job, job_id)
            if job is not None and job.status == "queued":
                await update_job_progress(session, job_id, status="running", progress=max(job.progress, 95))
            if job is not None and job.status in {"queued", "running"}:
                job = await update_job_progress(session, job_id, status="succeeded", progress=100)
                job.result = {"shot_id": shot.id, "render_id": render.id, "image_url": render.image_url}
                await session.commit()
            return
        if render.status == "failed":
            job = await session.get(Job, job_id)
            if job is not None and job.status in {"queued", "running"}:
                await update_job_progress(session, job_id, status="failed", error_msg=render.error_msg or "render failed")
                await session.commit()
            return
        if render.status == "running":
            job = await session.get(Job, job_id)
            if job is not None and job.status == "queued":
                await update_job_progress(session, job_id, status="running", progress=max(job.progress, 5))
                await session.commit()
            return

        try:
            await update_job_progress(session, job_id, status="running", progress=5)
            mark_shot_render_running(render)
            await session.commit()

            settings = get_settings()
            client = get_volcano_client()
            snapshot = render.prompt_snapshot or {}
            # M3b 统一把 confirmed references 作为 provider-consumable refs 传入；
            # service 层已经把 object key 归一成公网 URL / asset:// 引用，这里不再传裸 key。
            response = await client.image_generations(
                model=settings.ark_image_model,
                prompt=snapshot["prompt"],
                references=[item["image_url"] for item in snapshot.get("references", [])],
                n=1,
                size=getattr(settings, "ark_shot_image_size", "1024x1792"),
            )
            await update_job_progress(session, job_id, progress=55)
            await session.commit()

            temp_url = _extract_image_url(response)
            object_key = await persist_generated_asset(
                url=temp_url,
                project_id=shot.project_id,
                kind="shot",
                ext="png",
            )
            mark_shot_render_succeeded(shot, render, image_url=object_key)
            job = await update_job_progress(session, job_id, status="succeeded", progress=100)
            job.result = {"shot_id": shot.id, "render_id": render.id, "image_url": object_key}
            await session.commit()
        except VolcanoError as exc:
            msg = humanize_volcano_error_message(str(exc))
            mark_shot_render_failed(shot, render, error_code=_volcano_error_code(exc), error_msg=msg)
            await update_job_progress(session, job_id, status="failed", error_msg=msg)
            await session.commit()
        except Exception as exc:
            logger.exception("render_shot failed")
            mark_shot_render_failed(shot, render, error_code="internal_error", error_msg=str(exc))
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()


@celery_app.task(name="app.tasks.ai.render_shot.render_shot_task")
def render_shot_task(shot_id: str, render_id: str, job_id: str) -> None:
    asyncio.run(_render_shot_task(shot_id, render_id, job_id))
