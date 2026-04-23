import asyncio
import logging

from sqlalchemy import func, select

from app.domain.models import Character, Job
from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.tasks.ai.gen_character_asset import gen_character_asset
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await update_job_progress(session, job_id, status="running", progress=10)
            await session.commit()

            chars = (
                await session.execute(
                    select(Character).where(
                        Character.project_id == project_id,
                        Character.locked.is_(False),
                    )
                )
            ).scalars().all()
            locked_count = (
                await session.execute(
                    select(func.count(Character.id)).where(
                        Character.project_id == project_id,
                        Character.locked.is_(True),
                    )
                )
            ).scalar() or 0

            if not chars:
                job = await session.get(Job, job_id)
                if job is not None:
                    job.result = {"skipped_locked_count": int(locked_count)}
                await update_job_progress(session, job_id, status="succeeded", total=0, done=0, progress=100)
                await session.commit()
                return

            await update_job_progress(session, job_id, total=len(chars), done=0, progress=20)
            await session.commit()

            sub_tasks: list[tuple[str, str]] = []
            for char in chars:
                child = Job(
                    project_id=project_id,
                    parent_id=job_id,
                    kind="gen_character_asset_single",
                    status="queued",
                    target_type="character",
                    target_id=char.id,
                )
                session.add(child)
                await session.flush()
                sub_tasks.append((char.id, child.id))

            await session.commit()

            for char_id, child_id in sub_tasks:
                gen_character_asset.delay(char_id, child_id)
        except Exception as exc:
            logger.exception("regen character assets batch failed: %s", exc)
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()


@celery_app.task(name="ai.regen_character_assets_batch", queue="ai")
def regen_character_assets_batch(project_id: str, job_id: str) -> None:
    asyncio.run(_run(project_id, job_id))
