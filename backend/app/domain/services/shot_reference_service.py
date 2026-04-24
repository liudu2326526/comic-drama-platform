from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.config import get_settings
from app.domain.models import (
    Character,
    Project,
    ProjectReferenceAsset,
    Scene,
    ShotRender,
    ShotVideoRender,
    StoryboardShot,
)
from app.domain.schemas.reference import ReferenceAssetCreate, ReferenceCandidateRead
from app.domain.services.reference_candidates import build_reference_candidates
from app.infra.asset_store import build_asset_url
from app.infra.obs_store import get_obs_url, object_exists_in_obs


class ShotReferenceService:
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

    def _asset_ref(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("http://") or value.startswith("https://") or value.startswith("asset://"):
            return value
        return build_asset_url(value)

    async def list_candidates(self, project_id: str, shot_id: str) -> list[ReferenceCandidateRead]:
        await self._get_project(project_id)
        shot = await self._get_shot(project_id, shot_id)
        scenes = (
            await self.session.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.updated_at.desc())
            )
        ).scalars().all()
        characters = (
            await self.session.execute(
                select(Character).where(Character.project_id == project_id).order_by(Character.created_at)
            )
        ).scalars().all()

        items = [
            *build_reference_candidates(shot, scenes, characters, self._asset_ref),
            *(await self.list_history_assets(project_id)),
            *(await self.list_manual_assets(project_id)),
        ]
        return [ReferenceCandidateRead(**item) for item in dedupe_references(items)]

    async def list_history_assets(self, project_id: str) -> list[dict]:
        shots = (
            await self.session.execute(select(StoryboardShot.id).where(StoryboardShot.project_id == project_id))
        ).scalars().all()
        if not shots:
            return []

        image_renders = (
            await self.session.execute(
                select(ShotRender)
                .where(ShotRender.shot_id.in_(shots), ShotRender.status == "succeeded", ShotRender.image_url.isnot(None))
                .order_by(ShotRender.finished_at.desc(), ShotRender.created_at.desc())
            )
        ).scalars().all()
        video_renders = (
            await self.session.execute(
                select(ShotVideoRender)
                .where(
                    ShotVideoRender.shot_id.in_(shots),
                    ShotVideoRender.status == "succeeded",
                    ShotVideoRender.last_frame_url.isnot(None),
                )
                .order_by(ShotVideoRender.finished_at.desc(), ShotVideoRender.created_at.desc())
            )
        ).scalars().all()

        items: list[dict] = []
        for render in image_renders:
            image_url = self._asset_ref(render.image_url)
            if not image_url:
                continue
            items.append(
                {
                    "id": f"history:{render.id}",
                    "kind": "history",
                    "source_id": render.id,
                    "name": f"镜头图 v{render.version_no}",
                    "alias": f"镜头图 v{render.version_no}",
                    "mention_key": f"history:{render.id}",
                    "image_url": image_url,
                    "origin": "history",
                    "reason": "当前项目已生成镜头图",
                }
            )
        for video in video_renders:
            image_url = self._asset_ref(video.last_frame_url)
            if not image_url:
                continue
            items.append(
                {
                    "id": f"history:{video.id}:last_frame",
                    "kind": "history",
                    "source_id": video.id,
                    "name": f"视频尾帧 v{video.version_no}",
                    "alias": f"视频尾帧 v{video.version_no}",
                    "mention_key": f"history:{video.id}:last_frame",
                    "image_url": image_url,
                    "origin": "history",
                    "reason": "当前项目已生成视频尾帧",
                }
            )
        return items

    async def create_manual_asset(self, project_id: str, payload: ReferenceAssetCreate) -> ReferenceCandidateRead:
        await self._get_project(project_id)
        object_key = parse_project_asset_ref(project_id, payload.image_url)
        exists = await asyncio.to_thread(object_exists_in_obs, object_key)
        if not exists:
            raise ApiError(40401, "项目资产不存在或不可访问", http_status=404)

        asset = ProjectReferenceAsset(
            project_id=project_id,
            kind=payload.kind,
            name=payload.name.strip(),
            object_key=object_key,
            image_url=get_obs_url(object_key),
        )
        self.session.add(asset)
        await self.session.flush()
        return self._manual_asset_to_candidate(asset)

    async def list_manual_assets(self, project_id: str) -> list[dict]:
        rows = (
            await self.session.execute(
                select(ProjectReferenceAsset)
                .where(ProjectReferenceAsset.project_id == project_id)
                .order_by(ProjectReferenceAsset.created_at.desc())
            )
        ).scalars().all()
        return [self._manual_asset_to_candidate(row).model_dump(mode="json") for row in rows]

    @staticmethod
    def _manual_asset_to_candidate(asset: ProjectReferenceAsset) -> ReferenceCandidateRead:
        return ReferenceCandidateRead(
            id=f"manual:{asset.id}",
            kind="manual",
            source_id=asset.id,
            name=asset.name,
            alias=asset.name,
            mention_key=f"manual:{asset.id}",
            image_url=asset.image_url,
            origin="manual",
            reason="手动加入的项目参考图",
        )


def parse_project_asset_ref(project_id: str, value: str) -> str:
    raw = value.strip()
    prefix = f"projects/{project_id}/"
    if raw.startswith(prefix):
        return raw

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        public_base = get_settings().obs_public_base_url.rstrip("/")
        if not public_base or not raw.startswith(f"{public_base}/"):
            raise ApiError(40001, "参考图必须来自当前项目资产库", http_status=422)
        object_key = raw.removeprefix(f"{public_base}/").lstrip("/")
        if object_key.startswith(prefix):
            return object_key

    raise ApiError(40001, "参考图必须来自当前项目资产库", http_status=422)


def dedupe_references(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = str(item.get("mention_key") or item.get("id"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
