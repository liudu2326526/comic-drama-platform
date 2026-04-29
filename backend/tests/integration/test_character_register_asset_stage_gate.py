import pytest
from sqlalchemy import insert

from app.domain.models import Character
from tests.helpers import force_stage


@pytest.mark.asyncio
async def test_register_character_asset_allowed_after_character_stage(client, db_session):
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Register Asset Later Stage", "story": "Story content"},
    )
    project_id = response.json()["data"]["id"]

    await db_session.execute(
        insert(__import__("app.domain.models", fromlist=["Character"]).Character).values(
            id="C_LATER",
            project_id=project_id,
            name="LaterChar",
            role_type="supporting",
        )
    )
    await force_stage(db_session, project_id, "rendering")

    response = await client.post(f"/api/v1/projects/{project_id}/characters/C_LATER/register_asset")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["job_id"]


@pytest.mark.asyncio
async def test_register_character_asset_rejects_unsupported_visual_type(client, db_session):
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Reject Unsupported Portrait Type", "story": "Story content"},
    )
    project_id = response.json()["data"]["id"]

    db_session.add(
        Character(
            id="C_ANOMALY",
            project_id=project_id,
            name="异常吞噬暗影",
            role_type="antagonist",
            visual_type="anomaly_entity",
            is_humanoid=False,
            reference_image_url="https://example.com/anomaly.png",
        )
    )
    await force_stage(db_session, project_id, "rendering")

    response = await client.post(f"/api/v1/projects/{project_id}/characters/C_ANOMALY/register_asset")

    assert response.status_code == 403
    assert response.json()["code"] == 40301
    assert "当前角色类型不支持入人像库" in response.json()["message"]
