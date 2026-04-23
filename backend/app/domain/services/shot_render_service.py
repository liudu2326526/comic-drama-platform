from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.domain.models import Character, Project, Scene, ShotRender, StoryboardShot
from app.domain.schemas.shot_render import RenderSubmitRequest
from app.domain.services.reference_candidates import build_reference_candidates
from app.infra.asset_store import build_asset_url
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import (
    InvalidTransition,
    advance_to_ready_for_export_if_complete,
    advance_to_rendering,
    mark_shot_generating,
    mark_shot_locked,
    select_shot_render_version,
)


RENDERABLE_STAGES = {
    ProjectStageRaw.CHARACTERS_LOCKED.value,
    ProjectStageRaw.SCENES_LOCKED.value,
    ProjectStageRaw.RENDERING.value,
}


class ShotRenderService:
    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def build_render_draft(self, project_id: str, shot_id: str) -> dict:
        project = await self._get_project(project_id)
        if project.stage not in RENDERABLE_STAGES:
            raise InvalidTransition(project.stage, "render_draft", "只有 characters_locked/scenes_locked/rendering 阶段允许生成镜头草稿")

        shot = await self._get_shot(project_id, shot_id)
        scenes = (
            await self.session.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.updated_at.desc())
            )
        ).scalars().all()
        characters = (
            await self.session.execute(
                select(Character)
                .where(Character.project_id == project_id)
                .order_by(Character.created_at)
            )
        ).scalars().all()
        references = self._select_references(shot, scenes, characters)
        prompt = self._build_draft_prompt(shot, references)
        return {"shot_id": shot.id, "prompt": prompt, "references": references}

    async def create_render_version(
        self,
        project_id: str,
        shot_id: str,
        payload: RenderSubmitRequest,
    ) -> ShotRender:
        project = await self._get_project(project_id)
        if project.stage not in RENDERABLE_STAGES:
            raise InvalidTransition(project.stage, "render_shot", "只有 characters_locked/scenes_locked/rendering 阶段允许单镜头渲染")

        shot = (
            await self.session.execute(
                select(StoryboardShot)
                .where(StoryboardShot.id == shot_id, StoryboardShot.project_id == project_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if shot is None:
            raise ApiError(40401, "分镜不存在", http_status=404)
        if not payload.references:
            raise ValueError("至少需要 1 张参考图后才能确认生成")

        max_version = (
            await self.session.execute(
                select(func.max(ShotRender.version_no)).where(ShotRender.shot_id == shot_id)
            )
        ).scalar()
        render = ShotRender(
            shot_id=shot.id,
            version_no=(max_version or 0) + 1,
            status="queued",
            prompt_snapshot={
                "prompt": payload.prompt,
                "references": [item.model_dump() for item in payload.references],
                "shot": {
                    "id": shot.id,
                    "idx": shot.idx,
                    "title": shot.title,
                    "description": shot.description,
                    "detail": shot.detail,
                    "tags": shot.tags or [],
                },
            },
        )
        self.session.add(render)
        advance_to_rendering(project)
        mark_shot_generating(shot)
        await self.session.flush()
        return render

    def _asset_ref(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("http://") or value.startswith("https://") or value.startswith("asset://"):
            return value
        return build_asset_url(value)

    def _select_references(self, shot: StoryboardShot, scenes: list[Scene], characters: list[Character]) -> list[dict]:
        return build_reference_candidates(shot, scenes, characters, self._asset_ref)

    def _build_draft_prompt(self, shot: StoryboardShot, references: list[dict]) -> str:
        ref_descriptions = []
        for i, ref in enumerate(references):
            kind_zh = "主场景" if ref["kind"] == "scene" else "角色形象"
            ref_descriptions.append(f"图片{i+1}中的{kind_zh}({ref['name']})")

        header = f"镜头标题：{shot.title}\n镜头描述：{shot.description}\n镜头细节：{shot.detail or ''}\n"
        if not ref_descriptions:
            return f"{header}生成一张竖屏漫剧静帧，电影感构图，主体清晰。"

        ref_prompt = "，".join(ref_descriptions)
        return f"{header}请参考{ref_prompt}，生成一张竖屏漫剧静帧，电影感构图，主体清晰。"

    async def list_renders(self, project_id: str, shot_id: str) -> list[ShotRender]:
        await self._get_shot(project_id, shot_id)
        return (
            await self.session.execute(
                select(ShotRender).where(ShotRender.shot_id == shot_id).order_by(ShotRender.version_no.desc())
            )
        ).scalars().all()

    async def select_render(self, project_id: str, shot_id: str, render_id: str) -> StoryboardShot:
        shot = await self._get_shot(project_id, shot_id)
        render = await self.session.get(ShotRender, render_id)
        if render is None or render.shot_id != shot.id:
            raise ApiError(40401, "渲染版本不存在", http_status=404)
        select_shot_render_version(shot, render)
        await self.session.flush()
        return shot

    async def lock_shot(self, project_id: str, shot_id: str) -> StoryboardShot:
        project = await self._get_project(project_id)
        if project.stage not in {ProjectStageRaw.RENDERING.value, ProjectStageRaw.READY_FOR_EXPORT.value}:
            raise InvalidTransition(project.stage, "lock_shot", "只有 rendering/ready_for_export 阶段允许锁定镜头")
        shot = await self._get_shot(project_id, shot_id)
        if not shot.current_render_id:
            raise ValueError("镜头没有当前渲染版本，不能锁定")
        
        render = await self.session.get(ShotRender, shot.current_render_id)
        if render is None or render.shot_id != shot.id:
            raise ApiError(40401, "当前渲染版本已失效或不存在", http_status=404)
        if render.status != "succeeded":
            raise ValueError(f"当前渲染版本状态为 {render.status}，只有 succeeded 的版本可锁定")

        mark_shot_locked(shot)
        await self.session.flush()
        project = await self.session.get(Project, project_id)
        await advance_to_ready_for_export_if_complete(self.session, project)
        return shot
