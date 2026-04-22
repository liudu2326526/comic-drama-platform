from typing import Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Scene, Project, StoryboardShot
from app.domain.schemas.scene import SceneUpdate
from app.pipeline.transitions import assert_asset_editable, advance_to_scenes_locked


class SceneService:
    @staticmethod
    async def list_by_project(session: AsyncSession, project_id: str) -> Sequence[Scene]:
        stmt = select(Scene).where(Scene.project_id == project_id).order_by(Scene.created_at)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, scene_id: str) -> Scene | None:
        return await session.get(Scene, scene_id)

    @staticmethod
    async def update(
        session: AsyncSession, 
        project: Project, 
        scene: Scene, 
        update_data: SceneUpdate
    ) -> Scene:
        assert_asset_editable(project, "scene")
        
        data = update_data.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(scene, key, value)
        
        return scene

    @staticmethod
    async def lock(
        session: AsyncSession, 
        project: Project, 
        scene: Scene
    ) -> None:
        scene.locked = True
        
        # 尝试推进 stage
        try:
            await advance_to_scenes_locked(session, project)
        except Exception:
            pass

    @staticmethod
    async def bind_scene_to_shot(
        session: AsyncSession, 
        project_id: str, 
        shot_id: str, 
        scene_id: str
    ) -> StoryboardShot:
        # 校验项目和资源
        stmt = select(StoryboardShot).where(
            StoryboardShot.id == shot_id, 
            StoryboardShot.project_id == project_id
        )
        shot = (await session.execute(stmt)).scalar_one_or_none()
        if not shot:
            raise ValueError("分镜不存在")
            
        scene = await session.get(Scene, scene_id)
        if not scene or scene.project_id != project_id:
            raise ValueError("场景不存在或不属于该项目")
            
        shot.scene_id = scene_id
        return shot

    @staticmethod
    async def get_scene_usage(session: AsyncSession, project_id: str, scene_id: str) -> int:
        stmt = select(func.count(StoryboardShot.id)).where(
            StoryboardShot.project_id == project_id,
            StoryboardShot.scene_id == scene_id
        )
        return (await session.execute(stmt)).scalar() or 0
