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
    assert "角色视觉设定" in full_body
    assert "不得复用其他角色" in full_body
    assert "头像参考图" in headshot
    assert "面部清晰" in headshot
    assert "角色视觉设定" in headshot


def test_humanoid_character_prompts_list_required_visual_feature_fields():
    project = _project()
    character = SimpleNamespace(
        name="林川",
        summary="普通程序员",
        description="灾变下的普通程序员",
        is_humanoid=True,
    )

    prompts = [
        build_character_full_body_prompt(project, character),
        build_character_headshot_prompt(project, character),
    ]

    for prompt in prompts:
        assert "角色视觉设定：" in prompt
        assert "视觉特征字段" not in prompt
        assert "如果当前角色独有视觉特征未逐项写明" not in prompt
        assert "年龄段：" in prompt
        assert "体型轮廓：" in prompt
        assert "脸部气质：" in prompt
        assert "发型发色：" in prompt
        assert "服装层次：" in prompt
        assert "主色/辅色：" in prompt
        assert "鞋履/配件：" in prompt
        assert "唯一辨识点：" in prompt


def test_humanoid_character_prompt_uses_structured_visual_values():
    character = SimpleNamespace(
        name="林川",
        summary="普通程序员",
        description=(
            "年龄段：二十多岁；性别气质：克制冷静的青年男性；体型轮廓：清瘦中等身高、肩背略紧；"
            "脸部气质：窄脸、眼神警觉；发型发色：黑色短碎发、额前微乱；"
            "服装层次：深灰连帽内搭、浅灰机能夹克、黑色工装裤；主色/辅色：冷灰黑为主、少量蓝色发光线；"
            "鞋履/配件：黑色短靴、旧工牌挂绳；唯一辨识点：左袖有断裂蓝色芯片纹章"
        ),
        is_humanoid=True,
    )

    prompt = build_character_full_body_prompt(_project(), character)

    assert "年龄段：二十多岁" in prompt
    assert "性别气质：克制冷静的青年男性" in prompt
    assert "体型轮廓：清瘦中等身高、肩背略紧" in prompt
    assert "脸部气质：窄脸、眼神警觉" in prompt
    assert "发型发色：黑色短碎发、额前微乱" in prompt
    assert "服装层次：深灰连帽内搭、浅灰机能夹克、黑色工装裤" in prompt
    assert "主色/辅色：冷灰黑为主、少量蓝色发光线" in prompt
    assert "鞋履/配件：黑色短靴、旧工牌挂绳" in prompt
    assert "唯一辨识点：左袖有断裂蓝色芯片纹章" in prompt
    assert "结构化状态" not in prompt


def test_non_humanoid_character_prompt_uses_concept_sheet_not_human_standing_pose():
    character = SimpleNamespace(
        name="无定形异变物",
        summary="灾变来源",
        description="黑雾质感,边缘呈碎裂丝状,核心有冷白微光",
        is_humanoid=False,
    )

    full_body = build_character_full_body_prompt(_project(), character)
    headshot = build_character_headshot_prompt(_project(), character)

    assert "非人形" in full_body
    assert "单体概念设定图" in full_body
    assert "完整头发到鞋履" not in full_body
    assert "正面全身站姿" not in full_body
    assert "核心局部特写" in headshot
    assert "面部清晰" not in headshot


def test_scene_asset_prompt_keeps_no_person_constraints():
    prompt = build_scene_asset_prompt(_project(), _scene())

    assert "无人环境" in prompt
    assert "绝对不出现人物" in prompt
    assert "人群" in prompt
