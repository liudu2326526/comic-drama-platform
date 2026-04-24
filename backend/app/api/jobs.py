from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.envelope import ok
from app.api.errors import ApiError
from app.config import get_settings
from app.deps import get_db
from app.domain.models import Job, ShotVideoRender
from app.domain.services.job_progress_estimator import (
    duration_seconds,
    estimate_display_progress,
    video_progress_group,
)
from app.domain.services import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = JobService(db)
    job = await svc.get_job(job_id)
    if not job:
        raise ApiError(40401, "Job 不存在")

    settings = get_settings()
    recent_durations = await _recent_durations_for_job(db, job, settings.job_progress_history_size)
    estimate = estimate_display_progress(
        job,
        recent_durations=recent_durations,
        now=datetime.now(timezone.utc),
        default_seconds=settings.job_progress_default_seconds,
        min_seconds=settings.job_progress_estimate_min_seconds,
        cap=settings.job_progress_estimate_cap,
    )

    return ok({
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "display_progress": estimate.display_progress,
        "elapsed_seconds": estimate.elapsed_seconds,
        "estimated_total_seconds": estimate.estimated_total_seconds,
        "estimated_remaining_seconds": estimate.estimated_remaining_seconds,
        "estimated_source": estimate.estimated_source,
        "done": job.done,
        "total": job.total,
        "error_msg": job.error_msg,
        "target_type": job.target_type,
        "target_id": job.target_id,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "payload": job.payload,
        "result": job.result
    })


async def _recent_durations_for_job(db: AsyncSession, job: Job, limit: int) -> list[int]:
    if limit <= 0:
        return []
    stmt = (
        select(Job)
        .where(Job.kind == job.kind, Job.status == "succeeded", Job.finished_at.isnot(None))
        .order_by(Job.finished_at.desc())
        .limit(limit * 4)
    )
    rows = (await db.execute(stmt)).scalars().all()
    if job.kind != "render_shot_video":
        return [duration_seconds(row.created_at, row.finished_at) for row in rows[:limit]]

    target_group = await _video_job_group(db, job)
    durations: list[int] = []
    for row in rows:
        if await _video_job_group(db, row) != target_group:
            continue
        durations.append(duration_seconds(row.created_at, row.finished_at))
        if len(durations) >= limit:
            break
    return durations


async def _video_job_group(db: AsyncSession, job: Job) -> tuple[str | None, str | None, int | None]:
    payload = job.payload if isinstance(job.payload, dict) else {}
    render_id = payload.get("video_render_id")
    if render_id:
        video = await db.get(ShotVideoRender, render_id)
        if video is not None:
            return video_progress_group(video.params_snapshot)
    return video_progress_group(payload)
