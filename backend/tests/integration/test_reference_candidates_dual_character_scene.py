import pytest

from app.domain.models import Character, Project, Scene, StoryboardShot
from app.domain.services.shot_reference_service import ShotReferenceService


@pytest.mark.asyncio
async def test_candidates_include_character_full_body_headshot_and_scene_no_person(db_session):
    project = Project(name="雨夜", story="n", stage="scenes_locked", ratio="9:16")
    db_session.add(project)
    await db_session.flush()
    shot = StoryboardShot(project_id=project.id, idx=1, title="宫门雨夜", description="秦昭到宫门")
    character = Character(
        project_id=project.id,
        name="秦昭",
        role_type="supporting",
        full_body_image_url="projects/p1/characters/qz-full.png",
        headshot_image_url="projects/p1/characters/qz-head.png",
    )
    scene = Scene(project_id=project.id, name="朱雀门", theme="palace", reference_image_url="projects/p1/scenes/gate.png")
    db_session.add_all([shot, character, scene])
    await db_session.commit()

    candidates = await ShotReferenceService(db_session).list_candidates(project.id, shot.id)
    payloads = [item.model_dump(mode="json") for item in candidates]
    keys = {item["mention_key"] for item in payloads}

    assert "character:" + character.id in keys
    assert "character_headshot:" + character.id in keys
    assert "scene:" + scene.id in keys
    assert any(item["alias"] == "秦昭-全身" for item in payloads)
    assert any(item["alias"] == "秦昭-头像" for item in payloads)
