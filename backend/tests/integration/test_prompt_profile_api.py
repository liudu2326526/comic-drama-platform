import pytest

from app.domain.models import Character, Job, Project, Scene


async def seed_project(db_session, **kwargs) -> Project:
    data = {
        "name": "Prompt Profile Project",
        "story": "story",
        "stage": "draft",
        "ratio": "9:16",
    }
    data.update(kwargs)
    project = Project(**data)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


async def seed_character(db_session, project_id: str, **kwargs) -> Character:
    data = {
        "project_id": project_id,
        "name": "Character",
        "role_type": "supporting",
        "summary": "summary",
        "description": "description",
        "locked": False,
    }
    data.update(kwargs)
    character = Character(**data)
    db_session.add(character)
    await db_session.commit()
    await db_session.refresh(character)
    return character


async def seed_scene(db_session, project_id: str, **kwargs) -> Scene:
    data = {
        "project_id": project_id,
        "name": "Scene",
        "theme": "palace",
        "summary": "summary",
        "description": "description",
        "locked": False,
    }
    data.update(kwargs)
    scene = Scene(**data)
    db_session.add(scene)
    await db_session.commit()
    await db_session.refresh(scene)
    return scene


@pytest.mark.asyncio
async def test_project_detail_returns_prompt_profile_statuses(client, db_session):
    project = await seed_project(
        db_session,
        stage="storyboard_ready",
        character_prompt_profile_draft={"prompt": "雨夜宫廷", "source": "ai"},
        character_prompt_profile_applied={"prompt": "雨夜宫廷", "source": "ai"},
        scene_prompt_profile_draft={"prompt": "冷青皇城", "source": "manual"},
        scene_prompt_profile_applied={"prompt": "旧版皇城", "source": "ai"},
    )

    resp = await client.get(f"/api/v1/projects/{project.id}")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["characterPromptProfile"]["status"] == "applied"
    assert data["scenePromptProfile"]["status"] == "dirty"


@pytest.mark.asyncio
async def test_patch_character_prompt_profile_saves_draft(client, db_session):
    project = await seed_project(db_session, stage="storyboard_ready")

    resp = await client.patch(
        f"/api/v1/projects/{project.id}/prompt-profiles/character",
        json={"prompt": "统一冷雨古风宫廷"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["draft"]["prompt"] == "统一冷雨古风宫廷"
    assert data["draft"]["source"] == "manual"
    assert data["status"] == "draft_only"


@pytest.mark.asyncio
async def test_delete_scene_prompt_profile_draft_clears_draft_only(client, db_session):
    project = await seed_project(
        db_session,
        stage="characters_locked",
        scene_prompt_profile_draft={"prompt": "新稿", "source": "manual"},
        scene_prompt_profile_applied={"prompt": "旧稿", "source": "ai"},
    )

    resp = await client.delete(f"/api/v1/projects/{project.id}/prompt-profiles/scene/draft")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["draft"] is None
    assert data["applied"]["prompt"] == "旧稿"
    assert data["status"] == "applied"


@pytest.mark.asyncio
async def test_generate_character_prompt_profile_returns_job_ack(client, db_session, monkeypatch):
    project = await seed_project(db_session, stage="storyboard_ready")

    dispatched: dict[str, str] = {}

    def fake_delay(project_id: str, job_id: str) -> None:
        dispatched["project_id"] = project_id
        dispatched["job_id"] = job_id

    monkeypatch.setattr(
        "app.api.prompt_profiles.gen_character_prompt_profile.delay",
        fake_delay,
    )

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/generate")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["job_id"] == dispatched["job_id"]


@pytest.mark.asyncio
async def test_generate_character_prompt_profile_returns_409_when_same_lane_job_running(client, db_session):
    project = await seed_project(db_session, stage="storyboard_ready")
    db_session.add(
        Job(
            project_id=project.id,
            kind="gen_character_prompt_profile",
            status="running",
            progress=20,
        )
    )
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/generate")

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == 40901


@pytest.mark.asyncio
async def test_confirm_character_prompt_profile_applies_draft_and_starts_batch_regen(client, db_session, monkeypatch):
    project = await seed_project(
        db_session,
        stage="storyboard_ready",
        character_prompt_profile_draft={"prompt": "统一冷雨宫廷", "source": "manual"},
    )
    await seed_character(db_session, project_id=project.id, name="A", locked=False)

    dispatched: dict[str, str] = {}

    def fake_delay(project_id: str, job_id: str) -> None:
        dispatched["project_id"] = project_id
        dispatched["job_id"] = job_id

    monkeypatch.setattr("app.api.prompt_profiles.regen_character_assets_batch.delay", fake_delay)

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/confirm")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["job_id"] == dispatched["job_id"]

    detail_resp = await client.get(f"/api/v1/projects/{project.id}")
    detail = detail_resp.json()["data"]
    assert detail["characterPromptProfile"]["applied"]["prompt"] == "统一冷雨宫廷"


@pytest.mark.asyncio
async def test_confirm_character_prompt_profile_returns_409_when_asset_lane_running(client, db_session):
    project = await seed_project(
        db_session,
        stage="storyboard_ready",
        character_prompt_profile_draft={"prompt": "统一冷雨宫廷", "source": "manual"},
    )
    db_session.add(
        Job(
            project_id=project.id,
            kind="regen_character_assets_batch",
            status="queued",
            progress=0,
        )
    )
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/confirm")

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == 40901


@pytest.mark.asyncio
async def test_confirm_scene_prompt_profile_with_all_locked_targets_finishes_as_noop(client, db_session, monkeypatch):
    project = await seed_project(
        db_session,
        stage="characters_locked",
        scene_prompt_profile_draft={"prompt": "冷青皇城", "source": "manual"},
    )
    await seed_scene(db_session, project_id=project.id, name="S1", locked=True)

    def fail_delay(*args, **kwargs):
        raise AssertionError("should not dispatch child jobs when all scenes are locked")

    monkeypatch.setattr("app.api.prompt_profiles.regen_scene_assets_batch.delay", fail_delay)

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/scene/confirm")

    assert resp.status_code == 200
    ack = resp.json()["data"]
    assert ack["job_id"]

    job_resp = await client.get(f"/api/v1/jobs/{ack['job_id']}")
    job = job_resp.json()["data"]
    assert job["status"] == "succeeded"
    assert job["total"] == 0
    assert job["done"] == 0
    assert job["result"]["skipped_locked_count"] == 1
