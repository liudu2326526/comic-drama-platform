from datetime import datetime, timedelta, timezone

from app.domain.models import Job
from app.domain.services.job_progress_estimator import duration_seconds, estimate_display_progress


def test_estimate_uses_recent_duration_and_caps_running_progress():
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    job = Job(
        kind="render_shot_video",
        status="running",
        progress=5,
        created_at=now - timedelta(seconds=90),
    )

    estimate = estimate_display_progress(
        job,
        recent_durations=[100, 120, 140],
        now=now,
        default_seconds=300,
        min_seconds=10,
        cap=95,
    )

    assert estimate.display_progress == 75
    assert estimate.estimated_remaining_seconds == 30
    assert estimate.estimated_source == "recent_3"


def test_failed_job_freezes_elapsed_at_finished_at():
    created_at = datetime(2026, 4, 24, 12, 0)
    finished_at = created_at + timedelta(seconds=20)
    now = created_at.replace(tzinfo=timezone.utc) + timedelta(minutes=30)
    job = Job(
        kind="render_shot_video",
        status="failed",
        progress=23,
        created_at=created_at,
        finished_at=finished_at,
    )

    estimate = estimate_display_progress(
        job,
        recent_durations=[60],
        now=now,
        default_seconds=300,
        min_seconds=10,
        cap=95,
    )

    assert estimate.display_progress == 23
    assert estimate.elapsed_seconds == 20
    assert estimate.estimated_remaining_seconds is None


def test_duration_seconds_normalizes_naive_datetime_as_utc():
    start = datetime(2026, 4, 24, 12, 0)
    end = datetime(2026, 4, 24, 12, 1, tzinfo=timezone.utc)

    assert duration_seconds(start, end) == 60
