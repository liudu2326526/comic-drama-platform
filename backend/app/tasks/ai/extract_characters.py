import asyncio
import logging
import threading

from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

PLACEHOLDER_ERROR = "placeholder: extract_characters task not implemented yet"


async def _mark_placeholder_failed(job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await update_job_progress(session, job_id, status="running", progress=5)
            await update_job_progress(
                session,
                job_id,
                status="failed",
                progress=100,
                error_msg=PLACEHOLDER_ERROR,
            )
            await session.commit()
        except Exception:
            logger.exception("Failed to mark extract_characters placeholder job %s", job_id)
            raise


def _run_async(coro: object) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return

    error: list[BaseException] = []

    def runner() -> None:
        try:
            asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover - propagated below
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]


@celery_app.task(name="ai.extract_characters", queue="ai", bind=True)
def extract_characters(self, project_id: str, job_id: str) -> None:
    """Task 2 placeholder that always closes the job in a safe terminal state."""
    _run_async(_mark_placeholder_failed(job_id))
