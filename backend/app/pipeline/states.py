from enum import Enum


class ProjectStageRaw(str, Enum):
    DRAFT = "draft"
    STORYBOARD_READY = "storyboard_ready"
    CHARACTERS_LOCKED = "characters_locked"
    SCENES_LOCKED = "scenes_locked"
    RENDERING = "rendering"
    READY_FOR_EXPORT = "ready_for_export"
    EXPORTED = "exported"


STAGE_ORDER: list[ProjectStageRaw] = [
    ProjectStageRaw.DRAFT,
    ProjectStageRaw.STORYBOARD_READY,
    ProjectStageRaw.CHARACTERS_LOCKED,
    ProjectStageRaw.SCENES_LOCKED,
    ProjectStageRaw.RENDERING,
    ProjectStageRaw.READY_FOR_EXPORT,
    ProjectStageRaw.EXPORTED,
]

STAGE_ZH: dict[ProjectStageRaw, str] = {
    ProjectStageRaw.DRAFT: "草稿中",
    ProjectStageRaw.STORYBOARD_READY: "分镜已生成",
    ProjectStageRaw.CHARACTERS_LOCKED: "角色已锁定",
    ProjectStageRaw.SCENES_LOCKED: "场景已匹配",
    ProjectStageRaw.RENDERING: "镜头生成中",
    ProjectStageRaw.READY_FOR_EXPORT: "待导出",
    ProjectStageRaw.EXPORTED: "已导出",
}


def _index(stage: ProjectStageRaw) -> int:
    return STAGE_ORDER.index(stage)


def is_forward_allowed(current: ProjectStageRaw, target: ProjectStageRaw) -> bool:
    return _index(target) == _index(current) + 1


def is_rollback_allowed(current: ProjectStageRaw, target: ProjectStageRaw) -> bool:
    return _index(target) < _index(current)
