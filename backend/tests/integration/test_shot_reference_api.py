from datetime import datetime

import pytest

from app.domain.models import Character, Project, Scene, ShotRender, StoryboardShot
from app.infra.ulid import new_id


@pytest.mark.asyncio
async def test_reference_candidates_include_auto_and_history(client, db_session):
    project = Project(id=new_id(), name="P", story="S", stage="characters_locked", ratio="9:16")
    db_session.add(project)
    await db_session.commit()

    shot = StoryboardShot(
        id=new_id(),
        project_id=project.id,
        idx=1,
        title="宫门相见",
        description="秦昭进入长安殿",
        scene_id="SC1",
    )
    scene = Scene(
        id="SC1",
        project_id=project.id,
        name="长安殿",
        reference_image_url="https://img.example/scene.png",
    )
    character = Character(
        id="C1",
        project_id=project.id,
        name="秦昭",
        role_type="protagonist",
        reference_image_url="https://img.example/char.png",
    )
    db_session.add_all([shot, scene, character])
    await db_session.commit()

    render = ShotRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="succeeded",
        image_url="https://img.example/render.png",
        created_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db_session.add(render)
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/reference-candidates")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {item["origin"] for item in data} >= {"auto", "history"}
    assert any(item["mention_key"] == "scene:SC1" for item in data)
    assert any(item["id"] == f"history:{render.id}" for item in data)
