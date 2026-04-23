import pytest
from sqlalchemy import insert

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
