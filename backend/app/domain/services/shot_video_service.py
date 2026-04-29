from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.domain.models import Project, ShotVideoRender, StoryboardShot
from app.domain.schemas.shot_render import RenderSubmitReference
from app.domain.schemas.reference import ReferenceMention
from app.domain.services.reference_binding import build_reference_binding_text, normalize_reference_mentions
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import (
    InvalidTransition,
    advance_to_ready_for_export_if_complete,
    advance_to_rendering,
    mark_shot_generating,
    mark_shot_locked,
    return_to_rendering,
    select_shot_video_version,
)

VIDEO_RENDERABLE_STAGES = {
    ProjectStageRaw.CHARACTERS_LOCKED.value,
    ProjectStageRaw.SCENES_LOCKED.value,
    ProjectStageRaw.RENDERING.value,
    ProjectStageRaw.READY_FOR_EXPORT.value,
}

VIDEO_LOCK_STAGES = {
    ProjectStageRaw.RENDERING.value,
    ProjectStageRaw.READY_FOR_EXPORT.value,
}

RATIO_ALLOWLIST = {"9:16", "16:9", "1:1", "3:4", "4:3", "21:9"}


def normalize_video_ratio(value: str | None) -> str:
    if value and value in RATIO_ALLOWLIST:
        return value
    return "adaptive"


def resolve_video_model(settings: Settings, model_type: str) -> str:
    return settings.ark_video_model_fast if model_type == "fast" else settings.ark_video_model_standard


class ShotVideoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def _get_project(self, project_id: str) -> Project:
        project = await self.session.get(Project, project_id)
        if project is None:
            raise ApiError(40401, "项目不存在", http_status=404)
        return project

    async def _get_shot(self, project_id: str, shot_id: str) -> StoryboardShot:
        shot = await self.session.get(StoryboardShot, shot_id)
        if shot is None or shot.project_id != project_id:
            raise ApiError(40401, "分镜不存在", http_status=404)
        return shot

    async def create_video_version(
        self,
        project_id: str,
        shot_id: str,
        *,
        prompt: str,
        references: list[dict] | list[RenderSubmitReference],
        duration: int | None,
        resolution: str,
        model_type: str,
        generate_audio: bool = True,
        reference_audio_url: str | None = None,
        reference_mentions: list[ReferenceMention] | None = None,
    ) -> ShotVideoRender:
        project = await self._get_project(project_id)
        if project.stage not in VIDEO_RENDERABLE_STAGES:
            raise InvalidTransition(project.stage, "render_shot_video", "当前阶段不可生成镜头成片视频")
        if not prompt.strip():
            raise ValueError("请先生成或填写镜头提示词")
        if not references:
            raise ValueError("至少需要 1 张参考图后才能生成视频")
        if duration is not None and not (4 <= duration <= 15):
            raise ValueError("视频时长必须在 4-15 秒之间")
        if resolution not in {"480p", "720p"}:
            raise ValueError("分辨率仅支持 480p/720p")
        if model_type not in {"standard", "fast"}:
            raise ValueError("模型类型仅支持 standard/fast")

        shot = (
            await self.session.execute(
                select(StoryboardShot)
                .where(StoryboardShot.id == shot_id, StoryboardShot.project_id == project_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if shot is None:
            raise ApiError(40401, "分镜不存在", http_status=404)

        max_version = (
            await self.session.execute(select(func.max(ShotVideoRender.version_no)).where(ShotVideoRender.shot_id == shot_id))
        ).scalar()

        refs = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in references
        ]
        mentions = normalize_reference_mentions(reference_mentions)
        reference_binding_text = build_reference_binding_text(mentions)
        params_snapshot = {
            "resolution": resolution,
            "model_type": model_type,
            "resolved_model": resolve_video_model(self.settings, model_type),
            "ratio": normalize_video_ratio(project.ratio),
            "generate_audio": bool(generate_audio),
            "reference_audio_url": reference_audio_url,
            "watermark": False,
            "return_last_frame": True,
            "execution_expires_after": self.settings.ark_video_execution_expires_after,
        }
        if duration is not None:
            params_snapshot["duration"] = duration

        video = ShotVideoRender(
            shot_id=shot.id,
            version_no=(max_version or 0) + 1,
            status="queued",
            prompt_snapshot={
                "shot": {
                    "id": shot.id,
                    "idx": shot.idx,
                    "title": shot.title,
                    "description": shot.description,
                    "detail": shot.detail,
                    "tags": shot.tags or [],
                },
                "prompt": prompt,
                "references": refs,
                "reference_mentions": mentions,
                "reference_binding_text": reference_binding_text,
            },
            params_snapshot=params_snapshot,
        )
        self.session.add(video)
        if project.stage == ProjectStageRaw.READY_FOR_EXPORT.value:
            return_to_rendering(project)
        else:
            advance_to_rendering(project)
        mark_shot_generating(shot)
        await self.session.flush()
        return video

    async def list_videos(self, project_id: str, shot_id: str) -> list[ShotVideoRender]:
        await self._get_shot(project_id, shot_id)
        return (
            await self.session.execute(
                select(ShotVideoRender).where(ShotVideoRender.shot_id == shot_id).order_by(ShotVideoRender.version_no.desc())
            )
        ).scalars().all()

    async def select_video(self, project_id: str, shot_id: str, video_id: str) -> StoryboardShot:
        project = await self._get_project(project_id)
        if project.stage not in VIDEO_RENDERABLE_STAGES:
            raise InvalidTransition(project.stage, "select_video", "当前阶段不可切换视频版本")
        shot = await self._get_shot(project_id, shot_id)
        video = await self.session.get(ShotVideoRender, video_id)
        if video is None or video.shot_id != shot.id:
            raise ApiError(40401, "视频版本不存在", http_status=404)
        select_shot_video_version(shot, video)
        await self.session.flush()
        return shot

    async def lock_shot(self, project_id: str, shot_id: str) -> StoryboardShot:
        project = await self._get_project(project_id)
        if project.stage not in VIDEO_LOCK_STAGES:
            raise InvalidTransition(project.stage, "lock_shot", "只有 rendering/ready_for_export 阶段允许锁定镜头")
        shot = await self._get_shot(project_id, shot_id)
        if not shot.current_video_render_id:
            raise ValueError("镜头没有当前视频版本，不能锁定")

        video = await self.session.get(ShotVideoRender, shot.current_video_render_id)
        if video is None or video.shot_id != shot.id:
            raise ApiError(40401, "当前视频版本已失效或不存在", http_status=404)
        if video.status != "succeeded":
            raise ValueError(f"当前视频版本状态为 {video.status}，只有 succeeded 的版本可锁定")

        mark_shot_locked(shot)
        await self.session.flush()
        await advance_to_ready_for_export_if_complete(self.session, project)
        return shot
