import logging
from typing import Any
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.infra.asset_store import build_asset_url, persist_generated_asset
from app.domain.models import Character, Job, Project
from app.pipeline.transitions import update_job_progress
from app.tasks.async_runner import run_async_task
from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.tasks.ai.prompt_builders import build_character_full_body_prompt, build_character_headshot_prompt

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
                    error_msg=failure_msg or "部分角色资产生成失败",
                )
        elif done_count >= (parent_job.total or 0):
            await update_job_progress(session, parent_id, status="succeeded", progress=100)


async def run_character_asset_generation(character_id: str, job_id: str, *, session=None) -> None:
    if session is not None:
        await _run_character_asset_generation(session, character_id, job_id)
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _run_character_asset_generation(session, character_id, job_id)


async def _run_character_asset_generation(session, character_id: str, job_id: str) -> None:
    try:
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

        settings = get_settings()
        client = get_volcano_client()
        style_ref = build_asset_url(project.character_style_reference_image_url)
        style_refs = [style_ref] if style_ref else None

        if not char.full_body_image_url:
            full_body_resp = await client.image_generations(
                model=settings.ark_image_model,
                prompt=build_character_full_body_prompt(project, char),
                references=style_refs,
                n=1,
                size="1024x1024",
            )
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

        full_body_url = build_asset_url(full_body_key) if full_body_key else None
        headshot_refs = [url for url in [full_body_url, *(style_refs or [])] if url]
        headshot_resp = await client.image_generations(
            model=settings.ark_image_model,
            prompt=build_character_headshot_prompt(project, char),
            references=headshot_refs or None,
            n=1,
            size="1024x1024",
        )
        headshot_key = await persist_generated_asset(
            url=_extract_image_url(headshot_resp),
            project_id=char.project_id,
            kind="character_headshot",
            ext="png",
        )
        char.headshot_image_url = headshot_key

        await update_job_progress(session, job_id, status="succeeded", progress=100)
        await _update_parent_progress(session, job_id)
        await session.commit()
        logger.info("Character %s dual assets generated: %s, %s", character_id, full_body_key, headshot_key)
    except Exception as e:
        logger.exception("Error in gen_character_asset_task: %s", e)
        await update_job_progress(session, job_id, status="failed", error_msg=str(e))
        await _update_parent_progress(session, job_id, failure_msg=str(e))
        await session.commit()

@celery_app.task(name="ai.gen_character_asset", queue="ai", bind=True)
def gen_character_asset(self, character_id: str, job_id: str):
    run_async_task(run_character_asset_generation(character_id, job_id))
