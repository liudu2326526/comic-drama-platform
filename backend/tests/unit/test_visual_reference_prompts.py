from types import SimpleNamespace

from app.tasks.ai.prompt_builders import (
    build_character_full_body_prompt,
    build_character_headshot_prompt,
    build_character_style_reference_prompt,
    build_scene_asset_prompt,
    build_scene_style_reference_prompt,
)


def _project(**kwargs):
    data = {
        "name": "雨夜宫廷",
        "genre": "古风权谋",
        "story": "少年天子在雨夜登上朱雀门。",
        "summary": "雨夜权谋",
        "overview": "冷雨皇城",
        "character_prompt_profile_applied": {"prompt": "冷青灰，精致服饰"},
        "scene_prompt_profile_applied": {"prompt": "冷雨皇城，金石材质"},
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def _character():
    return SimpleNamespace(name="秦昭", summary="少年天子", description="黑金冕服")


def _scene():
    return SimpleNamespace(name="朱雀门", theme="palace", summary="雨夜宫门", description="石阶、宫灯、雨雾")


def test_character_style_reference_prompt_demands_white_background_full_body():
    prompt = build_character_style_reference_prompt(_project())

    assert "角色风格母版" in prompt
    assert "白底" in prompt
    assert "正面站姿" in prompt
    assert "禁止多人" in prompt


def test_scene_style_reference_prompt_forbids_people():
    prompt = build_scene_style_reference_prompt(_project())

    assert "无人场景风格母版" in prompt
    assert "绝对不出现人物" in prompt
    assert "人脸" in prompt
    assert "背影" in prompt


def test_character_dual_image_prompts_have_distinct_intent():
    full_body = build_character_full_body_prompt(_project(), _character())
    headshot = build_character_headshot_prompt(_project(), _character())

    assert "全身参考图" in full_body
    assert "完整头发到鞋履" in full_body
    assert "头像参考图" in headshot
    assert "面部清晰" in headshot


def test_scene_asset_prompt_keeps_no_person_constraints():
    prompt = build_scene_asset_prompt(_project(), _scene())

    assert "无人环境" in prompt
    assert "绝对不出现人物" in prompt
    assert "人群" in prompt
