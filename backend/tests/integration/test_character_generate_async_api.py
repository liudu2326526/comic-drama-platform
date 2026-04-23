import sys
import types

import pytest
from sqlalchemy import select

from app.domain.models import Job
from app.pipeline.states import ProjectStageRaw


@pytest.mark.asyncio
async def test_generate_characters_returns_extract_job_ack(
    client,
    db_session,
    project_factory,
):
    project = await project_factory(
        stage=ProjectStageRaw.STORYBOARD_READY.value,
        story="林夏在雨夜遇见周沉，两人一起追查剧院旧案。",
    )
    project_id = project.id

    calls: list[tuple[str, str]] = []

    def _delay(project_id: str, job_id: str) -> None:
        calls.append((project_id, job_id))

    fake_task = types.SimpleNamespace(delay=_delay)
    fake_module = types.ModuleType("app.tasks.ai.extract_characters")
    fake_module.extract_characters = fake_task
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(sys.modules, "app.tasks.ai.extract_characters", fake_module)

    try:
            resp = await client.post(f"/api/v1/projects/{project_id}/characters/generate", json={})
    finally:
        monkeypatch.undo()

    body = resp.json()

    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["job_id"]
    assert body["data"]["sub_job_ids"] == []

    await db_session.rollback()
    job = (
        await db_session.execute(select(Job).where(Job.id == body["data"]["job_id"]))
    ).scalar_one()
    assert job.project_id == project_id
    assert job.kind == "extract_characters"
    assert job.status == "queued"
    assert job.progress == 0
    assert job.done == 0
    assert job.total is None
    assert calls == [(project_id, job.id)]
