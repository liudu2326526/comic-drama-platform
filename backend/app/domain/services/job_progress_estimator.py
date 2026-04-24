from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.models import Job


@dataclass(frozen=True)
class JobProgressEstimate:
    display_progress: int
    elapsed_seconds: int
    estimated_total_seconds: int | None
    estimated_remaining_seconds: int | None
    estimated_source: str


def estimate_display_progress(
    job: Job,
    *,
    recent_durations: list[int],
    now: datetime,
    default_seconds: int,
    min_seconds: int,
    cap: int,
) -> JobProgressEstimate:
    if job.status == "succeeded":
        elapsed = duration_seconds(job.created_at, job.finished_at or now)
        return JobProgressEstimate(100, elapsed, elapsed or None, 0, "completed")

    end_time = job.finished_at if job.status in {"failed", "canceled"} and job.finished_at else now
    elapsed = duration_seconds(job.created_at, end_time)
    if job.status in {"failed", "canceled"}:
        return JobProgressEstimate(job.progress, elapsed, None, None, "terminal")

    if recent_durations:
        estimated_total = max(int(sum(recent_durations) / len(recent_durations)), min_seconds)
        source = f"recent_{len(recent_durations)}"
    else:
        estimated_total = max(default_seconds, min_seconds)
        source = "default"

    base_progress = job.progress or 0
    time_progress = int((elapsed / estimated_total) * 100) if estimated_total > 0 else 0
    display_progress = min(cap, max(base_progress, time_progress))
    remaining = max(estimated_total - elapsed, 0)
    return JobProgressEstimate(display_progress, elapsed, estimated_total, remaining, source)


def duration_seconds(start: datetime | None, end: datetime | None) -> int:
    if start is None or end is None:
        return 0
    return max(int((_aware_utc(end) - _aware_utc(start)).total_seconds()), 0)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def video_progress_group(payload: dict | None) -> tuple[str | None, str | None, int | None]:
    if not isinstance(payload, dict):
        return None, None, None
    model_type = payload.get("model_type")
    resolution = payload.get("resolution")
    duration = payload.get("duration")
    return (
        str(model_type) if model_type is not None else None,
        str(resolution) if resolution is not None else None,
        int(duration) if duration is not None else None,
    )
