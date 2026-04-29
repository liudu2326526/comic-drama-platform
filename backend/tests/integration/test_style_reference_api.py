import pytest

from app.domain.models import Job, Project


async def _seed_project(db_session, *, stage: str) -> Project:
    project = Project(name="Style Ref", story="story", ratio="9:16", stage=stage)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_generate_character_style_reference_returns_job_ack(client, db_session, monkeypatch):
    project = await _seed_project(db_session, stage="storyboard_ready")
    project_id = project.id
    dispatched: dict[str, str] = {}

    def fake_delay(project_id: str, job_id: str):
        dispatched["project_id"] = project_id
        dispatched["job_id"] = job_id

    monkeypatch.setattr("app.domain.services.style_reference_service.gen_character_style_reference.delay", fake_delay)

    resp = await client.post(f"/api/v1/projects/{project_id}/character-style-reference/generate")

    assert resp.status_code == 200
    assert resp.json()["data"]["job_id"] == dispatched["job_id"]
    await db_session.rollback()
    project = await db_session.get(Project, project_id)
    assert project.character_style_reference_status == "running"


@pytest.mark.asyncio
async def test_generate_scene_style_reference_returns_job_ack(client, db_session, monkeypatch):
    project = await _seed_project(db_session, stage="characters_locked")
    project.scene_prompt_profile_applied = {"prompt": "现代都市末世,冷色霓虹光影。"}
    await db_session.commit()
    dispatched: dict[str, str] = {}

    def fake_delay(project_id: str, job_id: str):
        dispatched["project_id"] = project_id
        dispatched["job_id"] = job_id

    monkeypatch.setattr("app.domain.services.style_reference_service.gen_scene_style_reference.delay", fake_delay)

    resp = await client.post(f"/api/v1/projects/{project.id}/scene-style-reference/generate")

    assert resp.status_code == 200
    assert resp.json()["data"]["job_id"] == dispatched["job_id"]


@pytest.mark.asyncio
async def test_generate_scene_style_reference_requires_applied_scene_profile(client, db_session):
    # Direct seeding keeps this test focused on the scene style-reference guard.
    project = await _seed_project(db_session, stage="characters_locked")
    project.scene_prompt_profile_draft = {"prompt": "现代都市末世,冷色霓虹光影。"}
    project.scene_prompt_profile_applied = None
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project.id}/scene-style-reference/generate")

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == 40901
    assert "请先确认场景统一视觉设定" in body["message"]


@pytest.mark.asyncio
async def test_generate_style_reference_rejects_same_lane_running_job(client, db_session):
    project = await _seed_project(db_session, stage="storyboard_ready")
    db_session.add(Job(project_id=project.id, kind="gen_character_style_reference", status="running", progress=20))
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project.id}/character-style-reference/generate")

    assert resp.status_code == 409
    assert resp.json()["code"] == 40901
