from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.pipeline.states import ProjectStageRaw, is_forward_allowed, is_rollback_allowed

if TYPE_CHECKING:
    from app.domain.models.project import Project


class InvalidTransition(Exception):
    def __init__(self, current: str, target: str, reason: str):
        self.current = current
        self.target = target
        self.reason = reason
        super().__init__(f"非法 stage 跃迁: {current} → {target} ({reason})")


@dataclass
class InvalidatedCounts:
    shots_reset: int = 0
    characters_unlocked: int = 0
    scenes_unlocked: int = 0


async def advance_stage(
    session: AsyncSession, project: Project, target: ProjectStageRaw
) -> None:
    current = ProjectStageRaw(project.stage)
    if not is_forward_allowed(current, target):
        raise InvalidTransition(current.value, target.value, "仅允许按顺序推进一阶")
    project.stage = target.value


async def rollback_stage(
    session: AsyncSession, project: Project, target: ProjectStageRaw
) -> InvalidatedCounts:
    current = ProjectStageRaw(project.stage)
    if not is_rollback_allowed(current, target):
        raise InvalidTransition(current.value, target.value, "只能回退到更早阶段")
    # M1: 下游表(storyboards/characters/scenes)尚未建,只改 stage;
    # M2 起此处按 spec §5.1 清理 scene_id / status / locked
    project.stage = target.value
    return InvalidatedCounts()
