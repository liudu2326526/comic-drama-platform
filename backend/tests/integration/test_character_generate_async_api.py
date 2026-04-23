import pytest
from sqlalchemy import select

from app.domain.models import Job
from app.pipeline.states import ProjectStageRaw
from app.tasks.ai.extract_characters import extract_characters


async def _create_storyboard_ready_project(project_factory):
    project = await project_factory(
        stage=ProjectStageRaw.STORYBOARD_READY.value,
        story="林夏在雨夜遇见周沉，两人一起追查剧院旧案。",
    )
    return project.id


async def _load_jobs(db_session, project_id: str) -> list[Job]:
    await db_session.rollback()
    return (
        await db_session.execute(
            select(Job).where(Job.project_id == project_id).order_by(Job.created_at, Job.id)
        )
    ).scalars().all()


@pytest.mark.asyncio
async def test_generate_characters_returns_extract_job_ack(
    client,
    db_session,
    project_factory,
    monkeypatch,
):
    project_id = await _create_storyboard_ready_project(project_factory)
    calls: list[tuple[str, str]] = []

    def fake_delay(pid: str, job_id: str) -> None:
        calls.append((pid, job_id))

    monkeypatch.setattr(extract_characters, "delay", fake_delay)

    resp = await client.post(f"/api/v1/projects/{project_id}/characters/generate", json={})
    body = resp.json()

    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["job_id"]
    assert body["data"]["sub_job_ids"] == []

    job = (await _load_jobs(db_session, project_id))[0]
    assert job.project_id == project_id
    assert job.kind == "extract_characters"
    assert job.status == "queued"
    assert job.progress == 0
    assert job.done == 0
    assert job.total is None
    assert calls == [(project_id, job.id)]


@pytest.mark.asyncio
async def test_generate_characters_marks_job_failed_when_dispatch_fails(
    client,
    db_session,
    project_factory,
    monkeypatch,
):
    project_id = await _create_storyboard_ready_project(project_factory)

    def fake_delay(pid: str, job_id: str) -> None:
        raise RuntimeError(f"boom for {pid}/{job_id}")

    monkeypatch.setattr(extract_characters, "delay", fake_delay)

    with pytest.raises(RuntimeError, match="boom for"):
        await client.post(f"/api/v1/projects/{project_id}/characters/generate", json={})

    jobs = await _load_jobs(db_session, project_id)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.kind == "extract_characters"
    assert job.status == "failed"
    assert job.error_msg is not None
    assert "dispatch failed:" in job.error_msg
    assert "boom for" in job.error_msg


@pytest.mark.asyncio
@pytest.mark.parametrize("job_kind", ["extract_characters", "gen_character_asset"])
async def test_generate_characters_rejects_when_generation_job_already_running(
    client,
    db_session,
    project_factory,
    job_kind,
):
    project_id = await _create_storyboard_ready_project(project_factory)
    job = Job(
        project_id=project_id,
        kind=job_kind,
        status="running",
        progress=40,
        done=1,
        total=3,
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project_id}/characters/generate", json={})
    body = resp.json()

    assert resp.status_code == 409
    assert body["code"] == 40901
    assert "已有角色生成任务进行中" in body["message"]


@pytest.mark.asyncio
async def test_extract_characters_placeholder_does_not_leave_job_queued(
    client,
    db_session,
    project_factory,
):
    project_id = await _create_storyboard_ready_project(project_factory)
    job = Job(
        project_id=project_id,
        kind="extract_characters",
        status="queued",
        progress=0,
        done=0,
        total=None,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    extract_characters.delay(project_id, job.id)

    jobs = await _load_jobs(db_session, project_id)
    assert len(jobs) == 1
    refreshed = jobs[0]
    assert refreshed.status == "failed"
    assert refreshed.error_msg is not None
    assert "placeholder" in refreshed.error_msg
    assert "not implemented" in refreshed.error_msg
