import pytest

from app.domain.models import Character, Project


@pytest.mark.asyncio
async def test_project_detail_returns_style_reference_and_dual_character_images(client, db_session):
    project = Project(
        name="雨夜",
        story="story",
        stage="storyboard_ready",
        ratio="9:16",
        character_style_reference_image_url="projects/p1/character_style_reference/ref.png",
        character_style_reference_prompt="角色母版 prompt",
        character_style_reference_status="succeeded",
        scene_style_reference_status="failed",
        scene_style_reference_error="boom",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="秦昭",
        role_type="supporting",
        reference_image_url="projects/p1/characters/legacy.png",
        full_body_image_url="projects/p1/characters/full.png",
        headshot_image_url="projects/p1/characters/head.png",
    )
    db_session.add(character)
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["characterStyleReference"]["status"] == "succeeded"
    assert data["characterStyleReference"]["prompt"] == "角色母版 prompt"
    assert data["characterStyleReference"]["imageUrl"].endswith("/character_style_reference/ref.png")
    assert data["sceneStyleReference"]["status"] == "failed"
    assert data["sceneStyleReference"]["error"] == "boom"
    saved_character = data["characters"][0]
    assert saved_character["reference_image_url"].endswith("/characters/full.png")
    assert saved_character["full_body_image_url"].endswith("/characters/full.png")
    assert saved_character["headshot_image_url"].endswith("/characters/head.png")
    assert saved_character["image_prompts"]["full_body"]
    assert "角色名称：秦昭" in saved_character["image_prompts"]["full_body"]
    assert "角色视觉设定" in saved_character["image_prompts"]["full_body"]
    assert "参考图使用规则：只参考参考图片的画风和服装质感" in saved_character["image_prompts"]["full_body"]
    assert "头像参考图" in saved_character["image_prompts"]["headshot"]
    assert "参考图使用规则：只参考参考图片的画风和服装质感" in saved_character["image_prompts"]["headshot"]
    assert "人物 360 度旋转参考视频" in saved_character["image_prompts"]["turnaround"]
    assert "角色名称：秦昭" not in saved_character["image_prompts"]["turnaround"]
