import re

from app.domain.models import Character, Project, Scene, StoryboardShot


def _profile_prompt(profile: dict | None) -> str | None:
    if isinstance(profile, dict):
        prompt = profile.get("prompt")
        if prompt:
            return str(prompt)
    return None


_STYLE_CLAUSE_KEYWORDS = (
    "视觉风格",
    "画风",
    "风格",
    "线条",
    "色彩",
    "调色",
    "色调",
    "颜色",
    "光照",
    "光影",
    "明暗",
    "阴影",
    "高光",
    "饱和",
    "材质",
    "质感",
    "渲染",
    "笔触",
    "构图",
    "景深",
    "人体比例",
    "人物比例",
    "写实",
    "漫剧",
    "漫画",
    "赛博",
    "废土",
    "悬疑",
    "恐怖",
    "氛围",
    "Q版",
)

_CONTEXT_CLAUSE_PREFIXES = (
    "世界时代",
    "故事",
    "剧情",
    "角色规则",
    "人物规则",
    "场景规则",
    "场景",
    "地点",
    "世界观",
    "时代背景",
    "核心场景",
)

_CONTEXT_CLAUSE_KEYWORDS = (
    "角色规则",
    "人物规则",
    "场景规则",
    "故事概要",
    "角色名称",
    "角色名",
    "具体角色",
)

_ENVIRONMENT_TERMS = (
    "天台",
    "高楼",
    "楼道",
    "城市",
    "城区",
    "末世城市",
    "摩天",
    "街道",
    "远处",
    "火光",
    "天空",
    "裂缝",
    "天空裂缝",
    "手机",
    "屏幕",
    "道具",
    "核心道具",
    "怪物",
    "影子怪物",
    "黑雾",
    "无定形",
    "场景",
    "背景",
    "建筑",
    "世界",
    "故事",
    "剧情",
    "地点",
)


def _redact_terms(text: str, terms: list[str] | tuple[str, ...], replacement: str = "角色") -> str:
    redacted = text
    for term in [term.strip() for term in terms if term and term.strip()]:
        redacted = redacted.replace(term, replacement)
    return redacted


def _split_prompt_clauses(text: str) -> list[str]:
    return [part.strip(" \t\r\n,，") for part in re.split(r"[；;。\n]+", text) if part.strip()]


def _split_phrase_parts(clause: str) -> list[str]:
    return [part.strip(" \t\r\n,，") for part in re.split(r"[，,、]+", clause) if part.strip()]


def _strip_environment_parts(clause: str) -> str:
    kept = [part for part in _split_phrase_parts(clause) if not any(term in part for term in _ENVIRONMENT_TERMS)]
    return "，".join(kept)


def _is_style_clause(clause: str) -> bool:
    normalized = clause.strip()
    if not normalized:
        return False
    if normalized.startswith(_CONTEXT_CLAUSE_PREFIXES) or any(
        keyword in normalized for keyword in _CONTEXT_CLAUSE_KEYWORDS
    ):
        return False
    if not any(keyword in normalized for keyword in _STYLE_CLAUSE_KEYWORDS):
        return False
    return bool(_strip_environment_parts(normalized))


def _style_only_character_profile(profile: dict | None, character_names: list[str] | None = None) -> str | None:
    prompt = _profile_prompt(profile)
    if not prompt:
        return None
    blocked_labels = ("角色名称", "角色名", "具体角色")
    blocked_names = [name.strip() for name in (character_names or []) if name and name.strip()]
    text = _redact_terms(str(prompt), blocked_labels)
    text = _redact_terms(text, blocked_names)
    clauses = [
        stripped
        for clause in _split_prompt_clauses(text)
        if _is_style_clause(clause)
        for stripped in [_strip_environment_parts(clause)]
        if stripped
    ]
    return "；".join(clauses).strip() or None


def _project_context(project: Project) -> tuple[str, str, str]:
    story = getattr(project, "story", "") or ""
    summary = getattr(project, "summary", None)
    overview = getattr(project, "overview", None)
    return (
        getattr(project, "name", "") or "",
        getattr(project, "genre", "") or "",
        summary or overview or story[:800],
    )


def build_character_style_reference_prompt(project: Project, *, character_names: list[str] | None = None) -> str:
    profile = _style_only_character_profile(project.character_prompt_profile_applied, character_names)
    _, genre, _ = _project_context(project)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一角色画风设定：\n{profile}")
    sections.append(
        f"题材类型仅用于校准美术时代感：{genre}\n"
        "用途：生成项目级角色画风母版/角色风格母版,只参考画风、线条、色彩、光影、服装材质、渲染方式和人物比例风格,不绑定具体剧情角色。\n"
        "画面要求：9:16竖屏,匿名中性示范人物,白底或极简浅灰背景,正面站姿,单人全身设定图。示范人物不代表任何项目角色。\n"
        "输入裁剪规则：只体现画风信息,不要体现具体人物身份、姓名、职业、年龄、性别、发型、脸型、剧情关系、地点、世界观事件、怪物、道具或背景叙事。\n"
        "继承规则：后续角色图只参考画风和材质质感,不得继承母版示范人物的姓名、身份、脸部特征或剧情关系。\n"
        "禁止项：禁止多人，禁止复杂场景，禁止具体剧情背景，禁止裁切身体，禁止道具遮挡主体，禁止文字水印，禁止风格漂移。"
    )
    return "\n\n".join(sections)


def build_scene_style_reference_prompt(project: Project) -> str:
    profile = _profile_prompt(project.scene_prompt_profile_applied)
    project_name, genre, story_context = _project_context(project)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级统一场景视觉设定：\n{profile}")
    sections.append(
        f"项目名称：{project_name}\n"
        f"题材：{genre}\n"
        f"故事概要：{story_context}\n"
        "用途：生成项目级无人场景风格母版，后续所有场景图以此统一空间结构、材质、色彩、天气与光影。\n"
        "画面要求：宽幅环境设定图，突出建筑/自然空间/道具层次，画面中绝对不出现人物。\n"
        "禁止项：绝对不出现人物、人脸、人群、背影、剪影、手脚、动物拟人角色；禁止文字水印，禁止风格漂移。"
    )
    return "\n\n".join(sections)


_HUMANOID_VISUAL_LABELS = (
    "年龄段",
    "性别气质",
    "体型轮廓",
    "脸部气质",
    "发型发色",
    "服装层次",
    "主色/辅色",
    "鞋履/配件",
    "唯一辨识点",
)

_NON_HUMANOID_VISUAL_LABELS = (
    "整体轮廓",
    "材质质感",
    "主色/辅色",
    "边缘形态",
    "核心视觉符号",
    "尺度感",
    "唯一辨识点",
)

_HUMANOID_MONSTER_VISUAL_LABELS = (
    "整体轮廓",
    "头部/面部结构",
    "身体结构",
    "材质质感",
    "主色/辅色",
    "肢体/运动方式",
    "威胁特征",
    "唯一辨识点",
)

_CREATURE_VISUAL_LABELS = (
    "整体轮廓",
    "身体结构",
    "材质质感",
    "主色/辅色",
    "运动方式",
    "攻击/交互特征",
    "尺度感",
    "唯一辨识点",
)

_ANOMALY_VISUAL_LABELS = (
    "形态边界",
    "材质/粒子质感",
    "颜色光效",
    "核心符号",
    "变化规律",
    "空间影响",
    "危险感",
    "唯一辨识点",
)

_OBJECT_VISUAL_LABELS = (
    "主体结构",
    "材质工艺",
    "交互界面",
    "发光区域",
    "状态变化",
    "尺度/摆放方式",
    "唯一辨识点",
)

_CROWD_VISUAL_LABELS = (
    "群体构成",
    "整体服装/形态",
    "颜色倾向",
    "数量密度",
    "行动姿态",
    "与场景关系",
    "唯一辨识点",
)

_ENVIRONMENT_FORCE_VISUAL_LABELS = (
    "空间形态",
    "影响范围",
    "材质/气象质感",
    "颜色光效",
    "动态变化",
    "对环境的破坏方式",
    "唯一辨识点",
)

_VISUAL_LABELS_BY_TYPE = {
    "human_actor": _HUMANOID_VISUAL_LABELS,
    "stylized_human": _HUMANOID_VISUAL_LABELS,
    "humanoid_monster": _HUMANOID_MONSTER_VISUAL_LABELS,
    "creature": _CREATURE_VISUAL_LABELS,
    "anomaly_entity": _ANOMALY_VISUAL_LABELS,
    "object_entity": _OBJECT_VISUAL_LABELS,
    "crowd_group": _CROWD_VISUAL_LABELS,
    "environment_force": _ENVIRONMENT_FORCE_VISUAL_LABELS,
}

_VISUAL_ASSET_LABELS = {
    "human_actor": ("全身参考图", "头像参考图", "360 度旋转参考视频"),
    "stylized_human": ("风格化全身参考图", "风格化头像参考图", "360 度旋转参考视频"),
    "humanoid_monster": ("类人怪物全身设定图", "头部/核心局部特写", "360 展示参考视频"),
    "creature": ("生物整体设定图", "核心器官/纹理特写", "动作参考视频"),
    "anomaly_entity": ("异常体概念设定图", "核心符号/粒子形态图", "动态特效参考视频"),
    "object_entity": ("物体/终端设定图", "细节/交互界面图", "状态变化参考视频"),
    "crowd_group": ("群体风貌参考图", None, None),
    "environment_force": ("环境/灾难源参考图", "特效/空间异常参考图", "环境特效参考视频"),
}

_HUMAN_LIKE_VISUAL_TYPES = {"human_actor", "stylized_human"}


_REFERENCE_IMAGE_USAGE_RULE = (
    "参考图使用规则：只参考参考图片的画风和服装质感；"
    "不得参考参考图片中的人脸、发型、体型、姿态、身份、背景或构图。"
)


def _reference_image_rule(has_reference_image: bool) -> str:
    return f"{_REFERENCE_IMAGE_USAGE_RULE}\n" if has_reference_image else ""


def _extract_visual_value(text: str, label: str, labels: tuple[str, ...]) -> str | None:
    later_labels = [item for item in labels if item != label]
    if not later_labels:
        pattern = rf"{re.escape(label)}[:：]\s*(.+)$"
    else:
        stop = "|".join(re.escape(item) + r"[:：]" for item in later_labels)
        pattern = rf"{re.escape(label)}[:：]\s*(.+?)(?:[；;\n]\s*(?:{stop})|$)"
    match = re.search(pattern, text, re.S)
    if not match:
        return None
    return match.group(1).strip(" \t\r\n；;。")


def _visual_spec_block(description: str | None, labels: tuple[str, ...]) -> str:
    text = (description or "").strip()
    has_structured_values = any(f"{label}：" in text or f"{label}:" in text for label in labels)
    lines: list[str] = []
    if has_structured_values:
        for label in labels:
            value = _extract_visual_value(text, label, labels)
            lines.append(f"{label}：{value or '未填写'}")
    else:
        if text:
            lines.append(f"原始描述：{text}")
        for label in labels:
            lines.append(f"{label}：未填写")
        lines.append("结构化状态：当前角色描述尚未按字段拆分，重新生成角色后会写入逐项具体值。")
    return "角色视觉设定：\n" + "\n".join(lines)


def _character_visual_type(char: Character) -> str:
    raw_visual_type = getattr(char, "visual_type", None)
    if raw_visual_type:
        visual_type = str(raw_visual_type)
        return visual_type if visual_type in _VISUAL_LABELS_BY_TYPE else "human_actor"
    if getattr(char, "is_humanoid", True) is False:
        return "anomaly_entity"
    return "human_actor"


def _visual_labels(char: Character) -> tuple[str, ...]:
    return _VISUAL_LABELS_BY_TYPE[_character_visual_type(char)]


def _asset_labels(char: Character) -> tuple[str, str | None, str | None]:
    return _VISUAL_ASSET_LABELS[_character_visual_type(char)]


def build_character_full_body_prompt(project: Project, char: Character, *, has_reference_image: bool = False) -> str:
    sections: list[str] = []
    visual_type = _character_visual_type(char)
    primary_label, _, _ = _asset_labels(char)
    visual_spec = _visual_spec_block(getattr(char, "description", None), _visual_labels(char))
    if visual_type in _HUMAN_LIKE_VISUAL_TYPES:
        visual_requirements = "画面要求：单人，白底或极简浅色背景，正面全身站姿，完整头发到鞋履，服饰层次和轮廓清晰。"
        negative_rules = "禁止项：禁止多人，禁止复杂背景，禁止裁切身体，禁止额外道具抢画面，禁止文字水印，禁止风格漂移。"
    elif visual_type == "crowd_group":
        visual_requirements = "画面要求：群体风貌参考图，白底或极简浅色背景，展示群体构成、服装/形态共性、数量密度和行动姿态；不要突出任何单一可入库人脸。"
        negative_rules = "禁止项：禁止单体头像，禁止人像库风格证件照，禁止复杂背景，禁止文字水印，禁止风格漂移。"
    else:
        visual_requirements = (
            "画面要求：非人形单体概念设定图，白底概念设定图，完整展示主体轮廓、材质质感、结构语言、核心视觉符号和尺度感；"
            "构图干净，主体清晰，不套用人类头像或站姿模板。"
        )
        negative_rules = (
            "禁止项：禁止多人，禁止复杂背景，禁止人类头发/五官/鞋履模板，禁止额外道具抢画面，禁止文字水印，禁止风格漂移。"
        )
    sections.append(
        f"用途：生成{primary_label}，用于后续分镜与视频生成的一致性锁定。\n"
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary or ''}\n"
        f"{visual_spec}\n"
        f"{_reference_image_rule(has_reference_image)}"
        "差异化要求：严格依据角色视觉设定生成；不得复用其他角色的发型、脸型、体型、服装配色、配件或标志性轮廓。\n"
        f"{visual_requirements}\n"
        f"{negative_rules}"
    )
    return "\n\n".join(sections)


def build_character_headshot_prompt(project: Project, char: Character, *, has_reference_image: bool = False) -> str | None:
    visual_type = _character_visual_type(char)
    _, secondary_label, _ = _asset_labels(char)
    if secondary_label is None:
        return None
    sections: list[str] = []
    visual_spec = _visual_spec_block(getattr(char, "description", None), _visual_labels(char))
    if visual_type in _HUMAN_LIKE_VISUAL_TYPES:
        purpose = f"用途：生成当前角色白底{secondary_label}，必须与当前角色全身参考图保持同一人物身份、发型、脸型与服装质感。"
        visual_requirements = "画面要求：单人，白底或极简浅色背景，胸像或肩部以上头像，面部清晰，五官稳定。"
        negative_rules = "禁止项：禁止多人，禁止遮挡面部，禁止夸张表情漂移，禁止文字水印，禁止风格漂移。"
    else:
        purpose = f"用途：生成当前角色白底{secondary_label}，必须与主参考图保持同一材质、轮廓语言和核心视觉符号。"
        visual_requirements = "画面要求：白底核心局部特写或细节特写，突出材质纹理、边缘形态、发光/纹理/结构符号；主体清晰，不做真人头像。"
        negative_rules = "禁止项：禁止多人，禁止复杂背景，禁止人类五官模板，禁止文字水印，禁止风格漂移。"
    sections.append(
        f"{purpose}\n"
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary or ''}\n"
        f"{visual_spec}\n"
        f"{_reference_image_rule(has_reference_image)}"
        "差异化要求：严格依据角色视觉设定生成；不得复用其他角色的发型、脸型、体型、服装配色、配件或标志性轮廓。\n"
        f"{visual_requirements}\n"
        f"{negative_rules}"
    )
    return "\n\n".join(sections)


def build_character_turnaround_prompt(
    project: Project,
    char: Character,
    *,
    character_names: list[str] | None = None,
    has_reference_image: bool = False,
) -> str | None:
    visual_type = _character_visual_type(char)
    _, _, motion_label = _asset_labels(char)
    if motion_label is None:
        return None
    sections: list[str] = []
    if visual_type in _HUMAN_LIKE_VISUAL_TYPES:
        sections.append(
            f"用途：生成当前人物 {motion_label},用于后续视频中保持人物全身造型一致。\n"
            "@图1（全身参考图）作为首帧约束,@图2（头像参考图）作为尾帧约束。\n"
            "主体始终是同一个人物,保持 @图1（全身参考图）中的服装、身材比例、发型、发色、五官气质一致,保持 @图2（头像参考图）中的脸部身份一致。\n"
            "背景为白色或极简干净棚拍背景,不添加复杂环境,不添加第二个人物。\n"
            "0-2s：画面从 @图1（全身参考图）开始,主体正面站立在画面中央,镜头固定中全身构图。主体看向镜头,用平稳、自然、清晰的语调开始说：“你好,我是角色形象参考”。\n"
            "2-6s：主体以身体中轴为中心,原地缓慢完成一次 360 度转身展示。转身过程必须清楚出现正面、右侧面、背面、左侧面，再回到正面。镜头保持稳定跟随,不做推拉摇移,不改变背景。身体比例稳定,服装稳定,发型稳定。\n"
            "6-7s：主体回到正面后,抬起一只手向镜头轻轻挥手 1-2 次,动作自然克制,手部不变形,身体站姿稳定。台词继续保持平稳语调,口型与“你好,我是角色形象参考”同步。\n"
            "7-8s：镜头从全身构图平稳推进到脸部近景,最终停在 @图2（头像参考图）的头像构图,脸部清晰稳定,表情自然。\n"
            "画质、风格与约束：9:16 竖屏,720p,8 秒,生成声音。画面清晰,角色身份一致,五官稳定,服装稳定,发型稳定,口型同步,动作顺滑。\n"
            "禁止多人,禁止换脸,禁止换衣服,禁止复杂背景,禁止文字水印,禁止肢体扭曲,禁止手指畸形,禁止只做镜头推近而不展示完整 360 度转身。"
        )
    else:
        visual_spec = _visual_spec_block(getattr(char, "description", None), _visual_labels(char))
        sections.append(
            f"用途：生成{motion_label},用于后续视频中保持非人物角色、物体、异常体或环境力量的动态表现一致。\n"
            "@图1（主参考图）与 @图2（细节参考图）只作为外观、材质、颜色和核心符号参考。\n"
            f"{visual_spec}\n"
            "画面要求：9:16 竖屏,720p,8 秒,白底或极简背景,主体清晰,动态展示其材质变化、形态变化、运动方式或特效状态。\n"
            "禁止项：禁止加入人类台词或发声表现,禁止生成真人头像,禁止复杂背景,禁止多人,禁止文字水印,禁止风格漂移。"
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
        "项目级场景视觉参考图使用规则：只参考整体美术风格、空间质感、色彩光影和材质语言；不要直接复制项目级场景母版的具体布局。当前输出必须以本场景名称、主题、简介和详述为准。\n"
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
