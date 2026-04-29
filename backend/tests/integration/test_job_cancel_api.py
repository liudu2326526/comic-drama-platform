import pytest

from app.domain.models import Job, Project, ShotVideoRender, StoryboardShot
from app.infra.db import get_session_factory
from app.pipeline.transitions import InvalidTransition, update_job_progress


@pytest.mark.asyncio
async def test_cancel_queued_job(client, db_session):
    job = Job(project_id=None, kind="gen_shot_draft", status="queued", progress=0)
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["id"] == job.id
    assert body["status"] == "canceled"
    await db_session.refresh(job)
    assert job.error_msg is None


@pytest.mark.asyncio
async def test_cancel_succeeded_job_is_conflict(client, db_session):
    job = Job(project_id=None, kind="gen_shot_draft", status="succeeded", progress=100)
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")

    assert resp.status_code == 409
    assert resp.json()["code"] == 40901


@pytest.mark.asyncio
async def test_canceled_job_cannot_be_overwritten_by_stale_worker_session(client, db_session):
    job = Job(project_id=None, kind="gen_shot_draft", status="queued", progress=0)
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    await db_session.get(Job, job.id)
    session_factory = get_session_factory()
    async with session_factory() as other:
        await update_job_progress(other, job.id, status="canceled")
        await other.commit()

    with pytest.raises(InvalidTransition):
        await update_job_progress(
            db_session,
            job.id,
            status="running",
            progress=90,
            done=1,
            total=2,
            error_msg="stale worker update",
        )

    await db_session.rollback()
    await db_session.refresh(job)
    assert job.status == "canceled"
    assert job.progress == 0
    assert job.done == 0
    assert job.total is None
    assert job.error_msg is None


@pytest.mark.asyncio
async def test_cancel_parent_job_cascades_to_active_children(client, db_session):
    parent = Job(project_id=None, kind="extract_characters", status="running", progress=50, total=2, done=0)
    db_session.add(parent)
    await db_session.flush()
    child_queued = Job(project_id=None, parent_id=parent.id, kind="gen_character_asset", status="queued")
    child_running = Job(project_id=None, parent_id=parent.id, kind="gen_character_asset", status="running")
    child_succeeded = Job(
        project_id=None,
        parent_id=parent.id,
        kind="gen_character_asset",
        status="succeeded",
        progress=100,
    )
    db_session.add_all([child_queued, child_running, child_succeeded])
    await db_session.commit()

    resp = await client.post(f"/api/v1/jobs/{parent.id}/cancel")

    assert resp.status_code == 200
    await db_session.refresh(parent)
    await db_session.refresh(child_queued)
    await db_session.refresh(child_running)
    await db_session.refresh(child_succeeded)
    assert parent.status == "canceled"
    assert child_queued.status == "canceled"
    assert child_running.status == "canceled"
    assert child_succeeded.status == "succeeded"
    assert child_queued.error_msg is None
    assert child_running.error_msg is None


@pytest.mark.asyncio
async def test_cancel_video_job_preserves_provider_cancelled_status(client, db_session, monkeypatch):
    class FakeVolcanoClient:
        async def video_generations_delete(self, task_id: str):
            return {"id": task_id, "status": "cancelled"}

    from app.api import jobs as jobs_api

    monkeypatch.setattr(jobs_api, "get_volcano_client", lambda: FakeVolcanoClient())
    project = Project(name="p", story="s", genre="现代末世", ratio="9:16")
    db_session.add(project)
    await db_session.flush()
    shot = StoryboardShot(project_id=project.id, idx=1, title="t", description="d")
    db_session.add(shot)
    await db_session.flush()
    video = ShotVideoRender(
        shot_id=shot.id,
        version_no=1,
        status="running",
        provider_task_id="seedance-task-1",
        provider_status="running",
    )
    db_session.add(video)
    await db_session.flush()
    job = Job(
        project_id=project.id,
        kind="render_shot_video",
        status="running",
        payload={"video_render_id": video.id},
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")

    assert resp.status_code == 200
    await db_session.refresh(video)
    assert video.provider_status == "cancelled"
