import logging
from typing import Any
from app.infra.asset_store import build_asset_url, persist_generated_asset
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.domain.models import Job, Project, Scene
from app.pipeline.transitions import update_job_progress
from app.tasks.async_runner import run_async_task
from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.tasks.ai.prompt_builders import build_scene_asset_prompt

logger = logging.getLogger(__name__)


def _extract_image_url(resp: Any) -> str:
    if isinstance(resp, dict):
        return resp["data"][0]["url"]
    return resp.data[0].url


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
                    error_msg=failure_msg or "部分场景资产生成失败",
                )
        elif done_count >= (parent_job.total or 0):
            await update_job_progress(session, parent_id, status="succeeded", progress=100)


async def run_scene_asset_generation(scene_id: str, job_id: str, *, session=None) -> None:
    if session is not None:
        await _run_scene_asset_generation(session, scene_id, job_id)
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _run_scene_asset_generation(session, scene_id, job_id)


async def _run_scene_asset_generation(session, scene_id: str, job_id: str) -> None:
    try:
        await update_job_progress(session, job_id, status="running", progress=10)
        await session.commit()

        scene = await session.get(Scene, scene_id)
        if not scene:
            logger.error("Scene %s not found", scene_id)
            await update_job_progress(session, job_id, status="failed", error_msg="Scene not found")
            await session.commit()
            return

        project = await session.get(Project, scene.project_id)
        if not project:
            logger.error("Project %s not found", scene.project_id)
            await update_job_progress(session, job_id, status="failed", error_msg="Project not found")
            await session.commit()
            return

        settings = get_settings()
        client = get_volcano_client()
        prompt = build_scene_asset_prompt(project, scene)
        style_ref = build_asset_url(project.scene_style_reference_image_url)
        references = [style_ref] if style_ref else None

        gen_resp = await client.image_generations(
            model=settings.ark_image_model,
            prompt=prompt,
            references=references,
            n=1,
            size="1344x768",
        )
        await update_job_progress(session, job_id, progress=55)
        await session.commit()

        object_key = await persist_generated_asset(
            url=_extract_image_url(gen_resp),
            project_id=scene.project_id,
            kind="scene",
            ext="png",
        )
        scene.reference_image_url = object_key
        await update_job_progress(session, job_id, status="succeeded", progress=100)
        await _update_parent_progress(session, job_id)
        await session.commit()
        logger.info("Scene %s asset generated and persisted: %s", scene_id, object_key)
    except Exception as e:
        logger.exception("Error in gen_scene_asset_task: %s", e)
        await update_job_progress(session, job_id, status="failed", error_msg=str(e))
        await _update_parent_progress(session, job_id, failure_msg=str(e))
        await session.commit()

@celery_app.task(name="ai.gen_scene_asset", queue="ai", bind=True)
def gen_scene_asset(self, scene_id: str, job_id: str):
    run_async_task(run_scene_asset_generation(scene_id, job_id))
