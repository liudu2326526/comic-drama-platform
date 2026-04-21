import pytest
from sqlalchemy import update

from app.domain.models import Project


async def _force_stage(db_session, project_id: str, stage: str) -> None:
    await db_session.execute(update(Project).where(Project.id == project_id).values(stage=stage))
    await db_session.commit()


@pytest.mark.asyncio
async def test_rollback_backward_ok(client, db_session):
    r = await client.post("/api/v1/projects", json={"name": "回退测试", "story": "x"})
    pid = r.json()["data"]["id"]
    await _force_stage(db_session, pid, "rendering")

    r = await client.post(
        f"/api/v1/projects/{pid}/rollback", json={"to_stage": "storyboard_ready"}
    )
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["from_stage"] == "rendering"
    assert body["data"]["to_stage"] == "storyboard_ready"
    assert body["data"]["invalidated"] == {
        "shots_reset": 0,
        "characters_unlocked": 0,
        "scenes_unlocked": 0,
    }


@pytest.mark.asyncio
async def test_rollback_forward_denied(client):
    r = await client.post("/api/v1/projects", json={"name": "回退前进", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/projects/{pid}/rollback", json={"to_stage": "rendering"})
    assert r.status_code == 403
    assert r.json()["code"] == 40301


@pytest.mark.asyncio
async def test_rollback_invalid_target(client):
    r = await client.post("/api/v1/projects", json={"name": "非法目标", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/projects/{pid}/rollback", json={"to_stage": "not_a_stage"})
    assert r.status_code == 422
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_rollback_same_stage_denied(client, db_session):
    r = await client.post("/api/v1/projects", json={"name": "同阶段", "story": "x"})
    pid = r.json()["data"]["id"]
    await _force_stage(db_session, pid, "storyboard_ready")
    r = await client.post(
        f"/api/v1/projects/{pid}/rollback", json={"to_stage": "storyboard_ready"}
    )
    assert r.status_code == 403
    assert r.json()["code"] == 40301
