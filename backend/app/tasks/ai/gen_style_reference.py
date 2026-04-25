import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.models import Project
from app.infra.asset_store import persist_generated_asset
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.pipeline.transitions import update_job_progress
from app.tasks.ai.prompt_builders import (
    build_character_style_reference_prompt,
    build_scene_style_reference_prompt,
)
from app.tasks.async_runner import run_async_task
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _extract_image_url(resp: Any) -> str:
    if isinstance(resp, dict):
        return resp["data"][0]["url"]
    return resp.data[0].url


async def _run_style_reference(
    project_id: str,
    job_id: str,
    *,
    kind: str,
    session: AsyncSession | None = None,
) -> None:
    if session is not None:
        await _run_style_reference_in_session(session, project_id, job_id, kind=kind)
        return

    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            await _run_style_reference_in_session(db, project_id, job_id, kind=kind)
    except Exception as exc:
        logger.exception("%s style reference generation failed", kind)
        session_factory = get_session_factory()
        async with session_factory() as fail_session:
            project = await fail_session.get(Project, project_id)
            if project:
                setattr(project, f"{kind}_style_reference_status", "failed")
                setattr(project, f"{kind}_style_reference_error", str(exc))
            try:
                await update_job_progress(fail_session, job_id, status="failed", error_msg=str(exc))
            except Exception:
                logger.exception("failed to mark style reference job failed")
            await fail_session.commit()


async def _run_style_reference_in_session(
    db: AsyncSession,
    project_id: str,
    job_id: str,
    *,
    kind: str,
) -> None:
    await update_job_progress(db, job_id, status="running", progress=10)
    project = await db.get(Project, project_id)
    if not project:
        await update_job_progress(db, job_id, status="failed", error_msg="Project not found")
        await db.commit()
        return

    prompt = (
        build_character_style_reference_prompt(project)
        if kind == "character"
        else build_scene_style_reference_prompt(project)
    )
    setattr(project, f"{kind}_style_reference_status", "running")
    setattr(project, f"{kind}_style_reference_prompt", prompt)
    setattr(project, f"{kind}_style_reference_error", None)
    await db.commit()

    settings = get_settings()
    response = await get_volcano_client().image_generations(
        settings.ark_image_model,
        prompt,
        n=1,
        size="1024x1024" if kind == "character" else "1344x768",
    )
    await update_job_progress(db, job_id, progress=55)
    await db.commit()

    object_key = await persist_generated_asset(
        url=_extract_image_url(response),
        project_id=project_id,
        kind=f"{kind}_style_reference",
        ext="png",
    )
    setattr(project, f"{kind}_style_reference_image_url", object_key)
    setattr(project, f"{kind}_style_reference_status", "succeeded")
    setattr(project, f"{kind}_style_reference_error", None)
    await update_job_progress(db, job_id, status="succeeded", progress=100)
    await db.commit()


async def run_character_style_reference(
    project_id: str,
    job_id: str,
    *,
    session: AsyncSession | None = None,
) -> None:
    await _run_style_reference(project_id, job_id, kind="character", session=session)


async def run_scene_style_reference(
    project_id: str,
    job_id: str,
    *,
    session: AsyncSession | None = None,
) -> None:
    await _run_style_reference(project_id, job_id, kind="scene", session=session)


@celery_app.task(name="ai.gen_character_style_reference", queue="ai", bind=True)
def gen_character_style_reference(self, project_id: str, job_id: str) -> None:
    run_async_task(run_character_style_reference(project_id, job_id))


@celery_app.task(name="ai.gen_scene_style_reference", queue="ai", bind=True)
def gen_scene_style_reference(self, project_id: str, job_id: str) -> None:
    run_async_task(run_scene_style_reference(project_id, job_id))
