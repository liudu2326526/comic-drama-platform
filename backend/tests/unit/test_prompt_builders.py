from types import SimpleNamespace

from app.tasks.ai.prompt_builders import build_character_asset_prompt, build_scene_asset_prompt


def test_build_character_asset_prompt_places_project_visual_profile_before_character_details():
    project = SimpleNamespace(
        character_prompt_profile_applied={
            "prompt": "中国现代雨夜都市，冷青灰色板，克制侧逆光，禁止风格漂移",
            "source": "ai",
        }
    )
    character = SimpleNamespace(name="萧临渊", summary="summary", description="description")

    prompt = build_character_asset_prompt(project, character)

    assert "项目级统一视觉设定" in prompt
    assert prompt.index("项目级统一视觉设定") < prompt.index("角色名称：萧临渊")
    assert "角色设定参考图" in prompt
    assert "禁止风格漂移" in prompt
    assert "角色名称：萧临渊" in prompt


def test_build_scene_asset_prompt_without_profile_keeps_baseline_scene_master_intent():
    project = SimpleNamespace(scene_prompt_profile_applied=None)
    scene = SimpleNamespace(name="朱雀门", theme="palace", summary="summary", description="description")

    prompt = build_scene_asset_prompt(project, scene)

    assert "场景名称：朱雀门" in prompt
    assert "项目级统一视觉设定" not in prompt
    assert "场景设定参考图" in prompt
