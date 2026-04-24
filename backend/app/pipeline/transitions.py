from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.pipeline.states import (
    STAGE_ORDER,
    ProjectStageRaw,
    is_forward_allowed,
    is_rollback_allowed,
)
from app.pipeline.storyboard_states import StoryboardStatus, is_storyboard_transition_allowed

if TYPE_CHECKING:
    from app.domain.models import Job, Project, Character


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


STORYBOARD_EDITABLE_STAGES: set[ProjectStageRaw] = {
    ProjectStageRaw.DRAFT,
    ProjectStageRaw.STORYBOARD_READY,
}


def assert_storyboard_editable(project: Project) -> None:
    """在 storyboards 写路径(新增/编辑/删除/reorder)调用。违反即 InvalidTransition → 40301。"""
    current = ProjectStageRaw(project.stage)
    if current not in STORYBOARD_EDITABLE_STAGES:
        raise InvalidTransition(
            current.value,
            "storyboard_edit",
            "只有 draft / storyboard_ready 阶段允许编辑分镜;请先 rollback",
        )


def assert_asset_editable(project: Project, kind: Literal["character", "scene"]) -> None:
    """在 characters / scenes 写路径调用。"""
    current = ProjectStageRaw(project.stage)
    if kind == "character":
        if current != ProjectStageRaw.STORYBOARD_READY:
            raise InvalidTransition(
                current.value,
                "character_edit",
                "只有 storyboard_ready 阶段允许编辑角色;请先 rollback",
            )
    elif kind == "scene":
        if current != ProjectStageRaw.CHARACTERS_LOCKED:
            raise InvalidTransition(
                current.value,
                "scene_edit",
                "只有 characters_locked 阶段允许编辑场景;请先 rollback",
            )


async def lock_protagonist(session: AsyncSession, project: Project, character: Character) -> None:
    """锁定项目主角,具有唯一性。使用 SELECT FOR UPDATE 确保并发安全。"""
    from app.domain.models import Character as CharacterModel
    
    current = ProjectStageRaw(project.stage)
    if current != ProjectStageRaw.STORYBOARD_READY:
        raise InvalidTransition(current.value, "lock_protagonist", "只有 storyboard_ready 阶段允许锁定主角")
        
    if character.project_id != project.id:
        raise InvalidTransition(project.id, character.project_id, "角色不属于该项目")

    # 锁定该项目所有角色行
    stmt = (
        select(CharacterModel)
        .where(CharacterModel.project_id == project.id)
        .with_for_update()
    )
    rows = (await session.execute(stmt)).scalars().all()
    
    found = False
    for r in rows:
        if r.id == character.id:
            r.is_protagonist = True
            r.role_type = "protagonist"
            r.locked = True
            found = True
        else:
            if r.is_protagonist:
                r.is_protagonist = False
                r.role_type = "supporting"
    
    if not found:
        # 如果 character 不在 rows 里, 说明传入的 character 对象有问题
        # 兜底处理
        character.is_protagonist = True
        character.role_type = "protagonist"
        character.locked = True
                # 注意:旧主角如果已经是 locked=True,这里保持 locked=True 还是 False? 
                # 按照 spec,降级为 supporting,locked 状态可以保留也可以由用户后续手动解锁
                # 这里为了严谨,仅改变角色身份
    
    await session.flush()


async def advance_to_characters_locked(session: AsyncSession, project: Project) -> None:
    """推进到 characters_locked 阶段。要求项目内至少有一个角色。"""
    from app.domain.models import Character
    
    current = ProjectStageRaw(project.stage)
    if current != ProjectStageRaw.STORYBOARD_READY:
        raise InvalidTransition(current.value, ProjectStageRaw.CHARACTERS_LOCKED.value, "当前阶段不可推进到角色锁定")

    stmt = select(func.count(Character.id)).where(
        Character.project_id == project.id,
    )
    count = (await session.execute(stmt)).scalar() or 0
    if count == 0:
        raise InvalidTransition(current.value, ProjectStageRaw.CHARACTERS_LOCKED.value, "项目内至少需要 1 个角色后才能进入场景设定")
    
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value


async def advance_to_scenes_locked(session: AsyncSession, project: Project) -> None:
    """推进到 scenes_locked 阶段。要求项目内至少有一个场景。"""
    from app.domain.models import Scene
    
    current = ProjectStageRaw(project.stage)
    if current != ProjectStageRaw.CHARACTERS_LOCKED:
        raise InvalidTransition(current.value, ProjectStageRaw.SCENES_LOCKED.value, "当前阶段不可推进到镜头生成")

    stmt = select(func.count(Scene.id)).where(Scene.project_id == project.id)
    scene_count = (await session.execute(stmt)).scalar() or 0
    if scene_count == 0:
        raise InvalidTransition(current.value, ProjectStageRaw.SCENES_LOCKED.value, "项目内至少需要 1 个场景后才能进入镜头生成")

    project.stage = ProjectStageRaw.SCENES_LOCKED.value


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
    from app.domain.models import StoryboardShot

    current = ProjectStageRaw(project.stage)
    if not is_rollback_allowed(current, target):
        raise InvalidTransition(current.value, target.value, "只能回退到更早阶段")

    counts = InvalidatedCounts()

    # 仅清理真正被"回退越过"的阶段产物(spec §5.1)。
    # 例:rendering → scenes_locked 只重置渲染状态,不动 scene 绑定与锁定。
    current_idx = STAGE_ORDER.index(current)
    target_idx = STAGE_ORDER.index(target)

    def crossed(threshold: ProjectStageRaw) -> bool:
        t = STAGE_ORDER.index(threshold)
        return current_idx >= t and target_idx < t

    # 1) 越过 RENDERING:清镜头渲染状态(shot_renders 历史与图片保留审计)
    if crossed(ProjectStageRaw.RENDERING):
        reset_render_stmt = (
            update(StoryboardShot)
            .where(StoryboardShot.project_id == project.id)
            .values(
                status=StoryboardStatus.PENDING.value,
                current_render_id=None,
            )
        )
        result = await session.execute(reset_render_stmt)
        counts.shots_reset = result.rowcount or 0

    # 2) 越过 SCENES_LOCKED:清 shot.scene_id
    if crossed(ProjectStageRaw.SCENES_LOCKED):
        clear_scene_stmt = (
            update(StoryboardShot)
            .where(StoryboardShot.project_id == project.id)
            .values(scene_id=None)
        )
        await session.execute(clear_scene_stmt)

    # 3) 越过 CHARACTERS_LOCKED: 不再解锁角色,保留历史计数为 0
    if crossed(ProjectStageRaw.CHARACTERS_LOCKED):
        counts.characters_unlocked = 0

    # 4) 最后改 project.stage
    project.stage = target.value
    return counts


async def update_job_progress(
    session: AsyncSession,
    job_id: str,
    *,
    done: int | None = None,
    total: int | None = None,
    progress: int | None = None,
    status: str | None = None,
    error_msg: str | None = None,
) -> Job:
    """唯一允许写 jobs.status/progress/done/total 的函数。"""
    from app.domain.models import Job

    job = await session.get(Job, job_id)
    if job is None:
        raise InvalidTransition("unknown_job", job_id, "job 不存在")
    if done is not None:
        job.done = done
    if total is not None:
        job.total = total
    if progress is not None:
        job.progress = max(0, min(100, progress))
    if error_msg is not None:
        job.error_msg = error_msg
    if status is not None:
        # 简单线性校验:queued→running→(succeeded|failed|canceled)
        allowed: dict[str, set[str]] = {
            "queued": {"running", "failed", "canceled"},
            "running": {"succeeded", "failed", "canceled"},
            "succeeded": set(),
            "failed": {"running"},   # 允许重试
            "canceled": set(),
        }
        if status not in allowed.get(job.status, set()) and status != job.status:
            raise InvalidTransition(job.status, status, "非法 job 状态跃迁")
        job.status = str(status)
        if status in {"succeeded", "failed", "canceled"}:
            job.finished_at = datetime.utcnow()
    return job


async def count_project_storyboards(session: AsyncSession, project_id: str) -> int:
    from app.domain.models import StoryboardShot

    stmt = select(StoryboardShot.id).where(StoryboardShot.project_id == project_id)
    rows = (await session.execute(stmt)).all()
    return len(rows)


def _set_storyboard_status(shot: object, target: StoryboardStatus, reason: str) -> None:
    current = StoryboardStatus(getattr(shot, "status"))
    if current == target:
        return
    if not is_storyboard_transition_allowed(current, target):
        raise InvalidTransition(current.value, target.value, reason)
    shot.status = target.value


def mark_shot_generating(shot: object) -> None:
    _set_storyboard_status(shot, StoryboardStatus.GENERATING, "当前镜头状态不可发起单镜头渲染")


def mark_shot_render_running(render: object) -> None:
    current = getattr(render, "status")
    if current != "queued":
        raise InvalidTransition(current, "running", "shot_render 只能 queued → running")
    render.status = "running"
    render.error_code = None
    render.error_msg = None


def mark_shot_render_succeeded(shot: object, render: object, *, image_url: str) -> None:
    current = getattr(render, "status")
    if current != "running":
        raise InvalidTransition(current, "succeeded", "shot_render 只能 running → succeeded")
    render.status = "succeeded"
    render.image_url = image_url
    render.finished_at = datetime.utcnow()
    _set_storyboard_status(shot, StoryboardStatus.SUCCEEDED, "当前镜头状态不可标记渲染成功")
    shot.current_render_id = render.id


def mark_shot_render_failed(
    shot: object,
    render: object,
    *,
    error_code: str,
    error_msg: str,
) -> None:
    current = getattr(render, "status")
    if current not in {"queued", "running"}:
        raise InvalidTransition(current, "failed", "shot_render 只能 queued/running → failed")
    render.status = "failed"
    render.error_code = error_code
    render.error_msg = error_msg
    render.finished_at = datetime.utcnow()
    _set_storyboard_status(shot, StoryboardStatus.FAILED, "当前镜头状态不可标记渲染失败")


def mark_shot_video_running(video_render: object) -> None:
    current = getattr(video_render, "status")
    if current != "queued":
        raise InvalidTransition(current, "running", "shot_video_render 只能 queued → running")
    video_render.status = "running"
    video_render.error_code = None
    video_render.error_msg = None


def mark_shot_video_succeeded(shot: object, video_render: object, *, video_url: str, last_frame_url: str | None) -> None:
    current = getattr(video_render, "status")
    if current != "running":
        raise InvalidTransition(current, "succeeded", "shot_video_render 只能 running → succeeded")
    video_render.status = "succeeded"
    video_render.video_url = video_url
    video_render.last_frame_url = last_frame_url
    video_render.finished_at = datetime.utcnow()
    _set_storyboard_status(shot, StoryboardStatus.SUCCEEDED, "当前镜头状态不可标记视频渲染成功")
    shot.current_video_render_id = video_render.id


def mark_shot_video_failed(
    shot: object,
    video_render: object,
    *,
    error_code: str,
    error_msg: str,
) -> None:
    current = getattr(video_render, "status")
    if current not in {"queued", "running"}:
        raise InvalidTransition(current, "failed", "shot_video_render 只能 queued/running → failed")
    video_render.status = "failed"
    video_render.error_code = error_code
    video_render.error_msg = error_msg
    video_render.finished_at = datetime.utcnow()
    _set_storyboard_status(shot, StoryboardStatus.FAILED, "当前镜头状态不可标记视频渲染失败")


def mark_shot_locked(shot: object) -> None:
    _set_storyboard_status(shot, StoryboardStatus.LOCKED, "只有 succeeded 镜头可锁定最终版")


def select_shot_render_version(shot: object, render: object) -> None:
    current = getattr(render, "status")
    if current != "succeeded":
        raise InvalidTransition(current, "select_render", "只能选择 succeeded 的渲染版本")
    shot.current_render_id = render.id
    _set_storyboard_status(shot, StoryboardStatus.SUCCEEDED, "当前镜头状态不可切换到成功版本")


def select_shot_video_version(shot: object, video_render: object) -> None:
    current = getattr(video_render, "status")
    if current != "succeeded":
        raise InvalidTransition(current, "select_video", "只能选择 succeeded 的视频版本")
    shot.current_video_render_id = video_render.id
    _set_storyboard_status(shot, StoryboardStatus.SUCCEEDED, "当前镜头状态不可切换到成功视频版本")


def advance_to_rendering(project: Project) -> None:
    current = ProjectStageRaw(project.stage)
    if current == ProjectStageRaw.RENDERING:
        return
    if current not in {ProjectStageRaw.CHARACTERS_LOCKED, ProjectStageRaw.SCENES_LOCKED}:
        raise InvalidTransition(current.value, ProjectStageRaw.RENDERING.value, "只有 characters_locked/scenes_locked 可进入 rendering")
    project.stage = ProjectStageRaw.RENDERING.value


def return_to_rendering(project: Project) -> None:
    current = ProjectStageRaw(project.stage)
    if current == ProjectStageRaw.RENDERING:
        return
    if current != ProjectStageRaw.READY_FOR_EXPORT:
        raise InvalidTransition(current.value, ProjectStageRaw.RENDERING.value, "只有 ready_for_export 可回到 rendering")
    project.stage = ProjectStageRaw.RENDERING.value


async def advance_to_ready_for_export_if_complete(session: AsyncSession, project: Project) -> bool:
    from app.domain.models import StoryboardShot

    current = ProjectStageRaw(project.stage)
    if current == ProjectStageRaw.READY_FOR_EXPORT:
        return True
    if current != ProjectStageRaw.RENDERING:
        return False
    rows = (
        await session.execute(
            select(StoryboardShot.status).where(StoryboardShot.project_id == project.id)
        )
    ).scalars().all()
    if rows and all(status in {"succeeded", "locked"} for status in rows):
        project.stage = ProjectStageRaw.READY_FOR_EXPORT.value
        return True
    return False
