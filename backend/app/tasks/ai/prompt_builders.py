from app.domain.models import Character, Project, Scene, StoryboardShot


def build_character_asset_prompt(project: Project, char: Character) -> str:
    profile = (project.character_prompt_profile_applied or {}).get("prompt")
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一视觉设定：\n{profile}")
    sections.append(
        f"用途：生成角色设定参考图，用于后续分镜与视频生成的一致性锁定。\n"
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary or ''}\n"
        f"角色详述：{char.description or ''}\n"
        "画面要求：单人，全身或七分身，主体明确，背景简洁，便于复用。\n"
        "禁止项：禁止多人，禁止复杂背景，禁止额外道具，禁止风格漂移，禁止文字水印。"
    )
    return "\n\n".join(sections)


def build_scene_asset_prompt(project: Project, scene: Scene) -> str:
    profile = (project.scene_prompt_profile_applied or {}).get("prompt")
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一视觉设定：\n{profile}")
    sections.append(
        f"用途：生成场景设定参考图，用于后续分镜静帧与视频镜头的场景一致性锁定。\n"
        f"场景名称：{scene.name}\n"
        f"场景主题：{scene.theme or ''}\n"
        f"场景简介：{scene.summary or ''}\n"
        f"场景详述：{scene.description or ''}\n"
        "画面要求：突出关键结构与空间层次，可弱化人物或不出现人物，便于复用。\n"
        "禁止项：禁止结构混乱，禁止无关人物抢画面，禁止时代错置，禁止风格漂移，禁止文字水印。"
    )
    return "\n\n".join(sections)


def build_storyboard_render_draft_prompt(
    project: Project,
    shot: StoryboardShot,
    references: list[dict],
) -> str:
    sections: list[str] = []
    character_profile = (project.character_prompt_profile_applied or {}).get("prompt")
    scene_profile = (project.scene_prompt_profile_applied or {}).get("prompt")
    if character_profile or scene_profile:
        sections.append(
            "项目级统一视觉设定：\n" + "\n".join(part for part in [character_profile, scene_profile] if part)
        )

    ref_lines = [f"图片{i + 1}：{ref['kind']} {ref['name']}" for i, ref in enumerate(references)]
    sections.append(
        f"镜头标题：{shot.title}\n"
        f"镜头描述：{shot.description}\n"
        f"镜头细节：{shot.detail or ''}\n"
        f"参考资产：\n" + ("\n".join(ref_lines) if ref_lines else "- 无")
    )
    sections.append(
        "镜头目标：突出主体关系与关键动作。\n"
        "构图要求：竖屏漫剧静帧，中近景优先，主体清晰。\n"
        "镜头语言：保持单一主运镜，注意前中后景层次与连续性。\n"
        "负向约束：禁止风格漂移，禁止无关人物，禁止字幕水印。"
    )
    return "\n\n".join(sections)
