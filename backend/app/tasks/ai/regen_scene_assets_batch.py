import asyncio
import logging

from sqlalchemy import func, select

from app.domain.models import Job, Scene
from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.tasks.ai.gen_scene_asset import gen_scene_asset
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await update_job_progress(session, job_id, status="running", progress=10)
            await session.commit()

            scenes = (
                await session.execute(
                    select(Scene).where(
                        Scene.project_id == project_id,
                        Scene.locked.is_(False),
                    )
                )
            ).scalars().all()
            locked_count = (
                await session.execute(
                    select(func.count(Scene.id)).where(
                        Scene.project_id == project_id,
                        Scene.locked.is_(True),
                    )
                )
            ).scalar() or 0

            if not scenes:
                job = await session.get(Job, job_id)
                if job is not None:
                    job.result = {"skipped_locked_count": int(locked_count)}
                await update_job_progress(session, job_id, status="succeeded", total=0, done=0, progress=100)
                await session.commit()
                return

            await update_job_progress(session, job_id, total=len(scenes), done=0, progress=20)
            await session.commit()

            sub_tasks: list[tuple[str, str]] = []
            for scene in scenes:
                child = Job(
                    project_id=project_id,
                    parent_id=job_id,
                    kind="gen_scene_asset_single",
                    status="queued",
                    target_type="scene",
                    target_id=scene.id,
                )
                session.add(child)
                await session.flush()
                sub_tasks.append((scene.id, child.id))

            await session.commit()

            for scene_id, child_id in sub_tasks:
                gen_scene_asset.delay(scene_id, child_id)
        except Exception as exc:
            logger.exception("regen scene assets batch failed: %s", exc)
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()


@celery_app.task(name="ai.regen_scene_assets_batch", queue="ai")
def regen_scene_assets_batch(project_id: str, job_id: str) -> None:
    asyncio.run(_run(project_id, job_id))
