import pytest
from sqlalchemy import select

from app.domain.models import Job
from app.pipeline.states import ProjectStageRaw


async def _create_storyboard_ready_project(project_factory):
    project = await project_factory(
        stage=ProjectStageRaw.STORYBOARD_READY.value,
        story="林夏在雨夜遇见周沉，两人一起追查剧院旧案。",
    )
    return project.id


@pytest.mark.asyncio
async def test_generate_characters_returns_extract_job_ack(
    client,
    db_session,
    project_factory,
):
    project_id = await _create_storyboard_ready_project(project_factory)

    resp = await client.post(f"/api/v1/projects/{project_id}/characters/generate", json={})
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
