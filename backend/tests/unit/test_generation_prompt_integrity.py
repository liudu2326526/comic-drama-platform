from types import SimpleNamespace

from app.tasks.ai.prompt_builders import (
    build_character_full_body_prompt,
    build_character_headshot_prompt,
    build_character_style_reference_prompt,
    build_character_turnaround_prompt,
    build_scene_asset_prompt,
)
from app.tasks.ai.gen_shot_draft import _build_prompt_messages


def test_character_style_reference_prompt_is_style_only_and_drops_character_names():
    project = SimpleNamespace(
        name="末世小说",
        genre="现代末世",
        story="现代城市断电后,影形生物入侵。" * 20,
        summary="林川和苏宁在现代城市断电后遭遇影形生物入侵。",
        overview="当代信息文明崩溃后的现代都市末世。",
        character_prompt_profile_applied={
            "prompt": "现代末世写实漫剧风格,低饱和冷灰光影。角色名林川、苏宁只属于具体角色,不应进入母版。"
        },
    )
    character_names = ["林川", "苏宁"]

    prompt = build_character_style_reference_prompt(project, character_names=character_names)

    assert "林川" not in prompt
    assert "苏宁" not in prompt
    assert "现代末世写实漫剧风格" in prompt
    assert "低饱和冷灰光影" in prompt
    assert "不绑定具体剧情角色" in prompt
    assert "只参考画风" in prompt


def test_character_style_reference_prompt_keeps_only_visual_style_not_character_or_scene_content():
    project = SimpleNamespace(
        name="末世小说",
        genre="科幻末世",
        story="林川和苏宁在二十层天台遭遇天空裂缝和影子怪物。" * 20,
        summary="程序员林川与伙伴苏宁在影子怪物入侵的末世退至天台。",
        overview="二十层高楼天台,天空裂缝,影子怪物。",
        character_prompt_profile_applied={
            "prompt": (
                "世界时代为影子怪物入侵后的科幻末世；"
                "视觉风格为硬派科幻漫剧写实风格，线条冷峻硬朗，低饱和深灰炭黑暗色调，明暗对比强烈，材质粗粝；"
                "角色规则为林川是清瘦东亚普通青年程序员，穿日常休闲工装，苏宁是短发女性；"
                "场景规则为二十层高楼天台，天空有细长白色裂缝，远处零星火光，影子怪物是无定形黑雾；"
                "负向规则为禁止Q版萌系人物造型，禁止高饱和鲜亮色调。"
            )
        },
    )

    prompt = build_character_style_reference_prompt(project, character_names=["林川", "苏宁"])

    assert "硬派科幻漫剧写实风格" in prompt
    assert "线条冷峻硬朗" in prompt
    assert "低饱和深灰炭黑暗色调" in prompt
    assert "明暗对比强烈" in prompt
    assert "材质粗粝" in prompt
    assert "清瘦东亚普通青年程序员" not in prompt
    assert "短发女性" not in prompt
    assert "日常休闲工装" not in prompt
    assert "二十层高楼天台" not in prompt
    assert "天空裂缝" not in prompt
    assert "影子怪物" not in prompt
    assert "故事概要" not in prompt
    assert "项目名称" not in prompt


def test_character_style_reference_prompt_drops_environment_descriptions_from_style_clauses():
    project = SimpleNamespace(
        name="末世小说",
        genre="科幻末世",
        story="林川和苏宁在二十层天台遭遇天空裂缝和影子怪物。" * 20,
        summary="程序员林川与伙伴苏宁在影子怪物入侵的末世退至天台。",
        overview="二十层高楼天台,天空裂缝,影子怪物。",
        character_prompt_profile_applied={
            "prompt": (
                "视觉风格为适配9:16竖屏的漫剧风格，融合赛博废土与科幻悬疑恐怖感，线条冷峻硬朗；"
                "调色光照整体以低饱和深灰、炭黑暗色调为主，只点缀远处零星火光的暖橙色、天空裂缝的冷白色、离线手机屏幕的冷蓝色荧光；"
                "镜头语言适配竖屏漫剧构图，多用中近景聚焦人物情绪与核心道具，大远景展现崩塌的末世城市全景；"
                "负向规则为禁止给影子怪物绘制固定的人形或明确怪物形态，禁止Q版萌系人物造型。"
            )
        },
    )

    prompt = build_character_style_reference_prompt(project, character_names=["林川", "苏宁"])

    assert "适配9:16竖屏" in prompt
    assert "低饱和深灰" in prompt
    assert "炭黑暗色调" in prompt
    assert "天台" not in prompt
    assert "天空裂缝" not in prompt
    assert "影子怪物" not in prompt
    assert "火光" not in prompt
    assert "手机" not in prompt
    assert "末世城市" not in prompt
    assert "核心道具" not in prompt


def test_headshot_prompt_prioritizes_current_character_identity():
    project = SimpleNamespace(character_prompt_profile_applied={"prompt": "现代末世写实漫剧风格"})
    char = SimpleNamespace(name="林川", summary="普通程序员", description="现代通勤休闲装,紧绷冷静")

    prompt = build_character_headshot_prompt(project, char)

    assert "角色名称：林川" in prompt
    assert "当前角色" in prompt
    assert "同一人物身份、发型、脸型与服装质感" in prompt
    assert "项目级母版示范人物" not in prompt


def test_character_image_prompts_do_not_include_project_character_visual_profile():
    project = SimpleNamespace(
        character_prompt_profile_applied={"prompt": "现代末世写实漫剧风格,低饱和冷灰光影"},
    )
    char = SimpleNamespace(
        name="林川",
        summary="普通程序员",
        description=(
            "年龄段：二十多岁；性别气质：克制冷静；体型轮廓：清瘦；脸部气质：眼神警觉；"
            "发型发色：黑色短碎发；服装层次：灰色夹克；主色/辅色：灰黑；"
            "鞋履/配件：黑色短靴；唯一辨识点：左袖蓝色芯片纹章"
        ),
    )

    image_prompts = [
        build_character_full_body_prompt(project, char),
        build_character_headshot_prompt(project, char),
    ]

    for prompt in image_prompts:
        assert "角色名称：林川" in prompt
        assert "角色视觉设定：" in prompt
        assert "现代末世写实漫剧风格" not in prompt
        assert "低饱和冷灰光影" not in prompt
        assert "项目级统一视觉设定" not in prompt
        assert "项目级角色画风设定" not in prompt

    turnaround_prompt = build_character_turnaround_prompt(project, char)
    assert "林川" not in turnaround_prompt
    assert "人物 360 度旋转参考视频" in turnaround_prompt
    assert "项目级统一视觉设定" not in turnaround_prompt
    assert "项目级角色画风设定" not in turnaround_prompt


def test_character_image_prompt_limits_reference_image_usage_when_reference_is_passed():
    project = SimpleNamespace(character_prompt_profile_applied=None)
    char = SimpleNamespace(
        name="林川",
        summary="普通程序员",
        description=(
            "年龄段：二十多岁；性别气质：克制冷静；体型轮廓：清瘦；脸部气质：眼神警觉；"
            "发型发色：黑色短碎发；服装层次：灰色夹克；主色/辅色：灰黑；"
            "鞋履/配件：黑色短靴；唯一辨识点：左袖蓝色芯片纹章"
        ),
    )

    image_prompts = [
        build_character_full_body_prompt(project, char, has_reference_image=True),
        build_character_headshot_prompt(project, char, has_reference_image=True),
    ]

    for prompt in image_prompts:
        assert "参考图使用规则：只参考参考图片的画风和服装质感" in prompt
        assert "不得参考参考图片中的人脸、发型、体型、姿态、身份、背景或构图" in prompt

    turnaround_prompt = build_character_turnaround_prompt(project, char, has_reference_image=True)
    assert "参考图使用规则" not in turnaround_prompt
    assert "@图1（全身参考图）作为首帧约束" in turnaround_prompt


def test_character_image_prompt_omits_reference_rule_without_reference_image():
    project = SimpleNamespace(character_prompt_profile_applied=None)
    char = SimpleNamespace(name="林川", summary="普通程序员", description="现代通勤休闲装")

    prompt = build_character_full_body_prompt(project, char)

    assert "参考图使用规则" not in prompt


def test_character_turnaround_prompt_requires_full_body_rotation_sheet():
    project = SimpleNamespace(character_prompt_profile_applied={"prompt": "现代末世写实漫剧风格"})
    char = SimpleNamespace(name="林川", summary="普通程序员", description="现代通勤休闲装")

    prompt = build_character_turnaround_prompt(project, char)

    assert "人物 360 度旋转参考视频" in prompt
    assert "@图1（全身参考图）作为首帧约束" in prompt
    assert "@图2（头像参考图）作为尾帧约束" in prompt
    assert "正面、右侧面、背面、左侧面，再回到正面" in prompt
    assert "服装稳定" in prompt
    assert "生成声音" in prompt


def test_character_turnaround_prompt_drops_project_profile_text():
    project = SimpleNamespace(
        character_prompt_profile_applied={
            "prompt": "林川的服装风格统一为低饱和冷灰,苏宁保持现代通勤材质。整体写实漫剧线条。"
        }
    )
    char = SimpleNamespace(name="林川", summary="普通程序员", description="现代通勤休闲装")

    prompt = build_character_turnaround_prompt(project, char, character_names=["林川", "苏宁"])

    assert "林川" not in prompt
    assert "苏宁" not in prompt
    assert "低饱和冷灰" not in prompt
    assert "现代通勤材质" not in prompt
    assert "整体写实漫剧线条" not in prompt
    assert "项目级角色画风设定" not in prompt
    assert "具体角色名" not in prompt


def test_scene_asset_prompt_uses_style_reference_without_copying_layout():
    project = SimpleNamespace(scene_prompt_profile_applied={"prompt": "现代都市末世,断电天台,冷灰低饱和"})
    scene = SimpleNamespace(
        name="全城断电天台眺望",
        theme="末世降临",
        summary="城市断电",
        description="高楼天台俯瞰现代城区",
    )

    prompt = build_scene_asset_prompt(project, scene)

    assert "现代都市末世" in prompt
    assert "不要直接复制项目级场景母版的具体布局" in prompt


def test_shot_draft_messages_include_applied_profiles_and_overview():
    context = {
        "project": {
            "id": "p1",
            "name": "末世小说",
            "genre": "现代末世",
            "ratio": "9:16",
            "summary": "现代城市断电后影形生物入侵。",
            "overview": "当代信息文明崩溃后的现代都市末世。",
            "character_prompt_profile": "现代通勤服装,写实悬疑漫剧风格。",
            "scene_prompt_profile": "现代都市天台,断电城区,冷灰夜景。",
        },
        "shot": {"title": "全城断电", "description": "林川看着现代城区熄灭", "detail": "", "tags": []},
        "skill_prompt": "Seedance prompt rules",
    }

    messages = _build_prompt_messages(context, [])
    joined = "\n".join(item["content"] for item in messages)

    assert "现代末世" in joined
    assert "当代信息文明崩溃后的现代都市末世" in joined
    assert "现代都市天台" in joined
    assert "项目题材、故事概要、项目概览和已应用视觉设定" in joined
