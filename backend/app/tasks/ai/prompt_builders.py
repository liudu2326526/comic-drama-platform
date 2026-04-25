from app.domain.models import Character, Project, Scene, StoryboardShot


def _profile_prompt(profile: dict | None) -> str | None:
    if isinstance(profile, dict):
        prompt = profile.get("prompt")
        if prompt:
            return str(prompt)
    return None


def build_character_style_reference_prompt(project: Project) -> str:
    profile = _profile_prompt(project.character_prompt_profile_applied)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一角色视觉设定：\n{profile}")
    sections.append(
        f"项目名称：{project.name}\n"
        f"题材：{project.genre or ''}\n"
        f"故事概要：{project.summary or project.overview or project.story[:800]}\n"
        "用途：生成项目级角色风格母版，后续所有角色图以此统一人物比例、服装质感、脸部风格与光影。\n"
        "画面要求：白底或极简浅色背景，正面站姿，单人全身设定图，头身比例清晰，服饰与时代质感明确。\n"
        "禁止项：禁止多人，禁止复杂场景，禁止裁切身体，禁止道具遮挡主体，禁止文字水印，禁止风格漂移。"
    )
    return "\n\n".join(sections)


def build_scene_style_reference_prompt(project: Project) -> str:
    profile = _profile_prompt(project.scene_prompt_profile_applied)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一场景视觉设定：\n{profile}")
    sections.append(
        f"项目名称：{project.name}\n"
        f"题材：{project.genre or ''}\n"
        f"故事概要：{project.summary or project.overview or project.story[:800]}\n"
        "用途：生成项目级无人场景风格母版，后续所有场景图以此统一空间结构、材质、色彩、天气与光影。\n"
        "画面要求：宽幅环境设定图，突出建筑/自然空间/道具层次，画面中绝对不出现人物。\n"
        "禁止项：绝对不出现人物、人脸、人群、背影、剪影、手脚、动物拟人角色；禁止文字水印，禁止风格漂移。"
    )
    return "\n\n".join(sections)


def build_character_full_body_prompt(project: Project, char: Character) -> str:
    profile = _profile_prompt(project.character_prompt_profile_applied)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一视觉设定：\n{profile}")
    sections.append(
        f"用途：生成角色白底全身参考图，用于后续分镜与视频生成的一致性锁定。\n"
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary or ''}\n"
        f"角色详述：{char.description or ''}\n"
        "画面要求：单人，白底或极简浅色背景，正面全身站姿，完整头发到鞋履，服饰层次和轮廓清晰。\n"
        "禁止项：禁止多人，禁止复杂背景，禁止裁切身体，禁止额外道具抢画面，禁止文字水印，禁止风格漂移。"
    )
    return "\n\n".join(sections)


def build_character_headshot_prompt(project: Project, char: Character) -> str:
    profile = _profile_prompt(project.character_prompt_profile_applied)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一视觉设定：\n{profile}")
    sections.append(
        f"用途：生成角色白底头像参考图，必须与全身参考图保持同一人物身份、发型、脸型与服装质感。\n"
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary or ''}\n"
        f"角色详述：{char.description or ''}\n"
        "画面要求：单人，白底或极简浅色背景，胸像或肩部以上头像，面部清晰，五官稳定。\n"
        "禁止项：禁止多人，禁止遮挡面部，禁止夸张表情漂移，禁止文字水印，禁止风格漂移。"
    )
    return "\n\n".join(sections)


def build_character_asset_prompt(project: Project, char: Character) -> str:
    return build_character_full_body_prompt(project, char)


def build_scene_asset_prompt(project: Project, scene: Scene) -> str:
    profile = _profile_prompt(project.scene_prompt_profile_applied)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一视觉设定：\n{profile}")
    sections.append(
        f"用途：生成场景设定参考图，用于后续分镜静帧与视频镜头的场景一致性锁定。\n"
        f"场景名称：{scene.name}\n"
        f"场景主题：{scene.theme or ''}\n"
        f"场景简介：{scene.summary or ''}\n"
        f"场景详述：{scene.description or ''}\n"
        "画面要求：突出关键结构与空间层次，只生成无人环境、建筑、道具、天气与光影，便于复用。\n"
        "禁止项：绝对不出现人物、人脸、人群、背影、剪影、手脚、动物拟人角色；禁止结构混乱，禁止时代错置，禁止风格漂移，禁止文字水印。"
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
