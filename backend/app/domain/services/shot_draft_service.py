from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.domain.models import Character, Job, Project, Scene, ShotDraft, StoryboardShot
from app.infra.asset_store import build_asset_url
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import InvalidTransition
from app.domain.services.reference_candidates import build_reference_candidates


DRAFT_RENDERABLE_STAGES = {
    ProjectStageRaw.CHARACTERS_LOCKED.value,
    ProjectStageRaw.SCENES_LOCKED.value,
    ProjectStageRaw.RENDERING.value,
}


@lru_cache(maxsize=1)
def load_seedance_prompt_skill() -> str:
    skill_path = Path(__file__).resolve().parents[4] / "docs" / "huoshan_api" / "SKILL.md"
    return skill_path.read_text(encoding="utf-8")


class ShotDraftService:
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

    async def ensure_draft_renderable(self, project_id: str, shot_id: str) -> StoryboardShot:
        project = await self._get_project(project_id)
        if project.stage not in DRAFT_RENDERABLE_STAGES:
            raise InvalidTransition(
                project.stage,
                "render_draft",
                "只有 characters_locked/scenes_locked/rendering 阶段允许生成镜头草稿",
            )
        return await self._get_shot(project_id, shot_id)

    async def ensure_no_active_draft_job(self, project_id: str, shot_id: str) -> None:
        stmt = select(Job.id).where(
            Job.project_id == project_id,
            Job.kind == "gen_shot_draft",
            Job.target_id == shot_id,
            Job.status.in_(["queued", "running"]),
        )
        exists = (await self.session.execute(stmt)).scalar_one_or_none()
        if exists:
            raise ValueError("该镜头已有草稿生成任务进行中")

    async def get_latest_draft(self, project_id: str, shot_id: str) -> ShotDraft | None:
        await self._get_project(project_id)
        await self._get_shot(project_id, shot_id)
        stmt = (
            select(ShotDraft)
            .where(ShotDraft.shot_id == shot_id)
            .order_by(ShotDraft.version_no.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def build_generation_context(self, project_id: str, shot_id: str) -> dict:
        project = await self._get_project(project_id)
        shot = await self._get_shot(project_id, shot_id)
        scenes = (
            await self.session.execute(
                select(Scene)
                .where(Scene.project_id == project_id)
                .order_by(Scene.updated_at.desc())
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
        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "genre": project.genre,
                "ratio": project.ratio,
                "summary": project.summary,
                "overview": project.overview,
                "character_prompt_profile": (project.character_prompt_profile_applied or {}).get("prompt"),
                "scene_prompt_profile": (project.scene_prompt_profile_applied or {}).get("prompt"),
            },
            "shot": {
                "id": shot.id,
                "idx": shot.idx,
                "title": shot.title,
                "description": shot.description,
                "detail": shot.detail,
                "tags": shot.tags or [],
            },
            "reference_candidates": references,
            "skill_prompt": load_seedance_prompt_skill(),
        }

    async def create_draft(
        self,
        *,
        shot_id: str,
        prompt: str,
        references: list[dict],
        optimizer_snapshot: dict | None,
        source_snapshot: dict,
    ) -> ShotDraft:
        max_version = (
            await self.session.execute(
                select(func.max(ShotDraft.version_no)).where(ShotDraft.shot_id == shot_id)
            )
        ).scalar()
        draft = ShotDraft(
            shot_id=shot_id,
            version_no=(max_version or 0) + 1,
            prompt=prompt,
            references_snapshot=references,
            optimizer_snapshot=optimizer_snapshot,
            source_snapshot=source_snapshot,
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    def _asset_ref(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("http://") or value.startswith("https://") or value.startswith("asset://"):
            return value
        return build_asset_url(value)

    def _select_references(
        self,
        shot: StoryboardShot,
        scenes: list[Scene],
        characters: list[Character],
    ) -> list[dict]:
        return build_reference_candidates(shot, scenes, characters, self._asset_ref)
