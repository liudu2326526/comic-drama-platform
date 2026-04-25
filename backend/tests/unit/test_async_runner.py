import threading
import time

import pytest

from app.tasks.async_runner import dispatch_task_group


@pytest.mark.asyncio
async def test_dispatch_task_group_runs_delay_calls_concurrently() -> None:
    active = 0
    max_active = 0
    calls: list[tuple[str, str]] = []
    lock = threading.Lock()

    class FakeTask:
        def delay(self, item_id: str, job_id: str) -> None:
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.05)
                calls.append((item_id, job_id))
            finally:
                with lock:
                    active -= 1

    await dispatch_task_group(
        FakeTask(),
        [("item-1", "job-1"), ("item-2", "job-2"), ("item-3", "job-3")],
    )

    assert max_active > 1
    assert sorted(calls) == [
        ("item-1", "job-1"),
        ("item-2", "job-2"),
        ("item-3", "job-3"),
    ]

