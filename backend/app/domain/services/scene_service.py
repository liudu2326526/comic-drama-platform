from typing import Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.domain.models import Scene, Project, StoryboardShot
from app.domain.schemas.scene import SceneUpdate
from app.pipeline.transitions import assert_asset_editable

logger = logging.getLogger(__name__)


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
    async def bind_scene_to_shot(
        session: AsyncSession, 
        project_id: str, 
        shot_id: str, 
        scene_id: str
    ) -> tuple[StoryboardShot, Scene]:
        project = await session.get(Project, project_id)
        if not project:
            raise ValueError("项目不存在")
        assert_asset_editable(project, "scene")

        # 校验分镜和场景
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
        return shot, scene

    @staticmethod
    async def get_scene_usage(session: AsyncSession, project_id: str, scene_id: str) -> int:
        stmt = select(func.count(StoryboardShot.id)).where(
            StoryboardShot.project_id == project_id,
            StoryboardShot.scene_id == scene_id
        )
        return (await session.execute(stmt)).scalar() or 0

    @staticmethod
    async def generate_async(session: AsyncSession, project: Project) -> str:
        """异步场景生成: 创建 gen_scene_asset job 并投递任务"""
        from app.tasks.ai.extract_scenes import extract_scenes
        from app.domain.services.job_service import JobService
        from app.pipeline.transitions import update_job_progress

        assert_asset_editable(project, "scene")

        # 1. 创建 Job
        job = await JobService(session).create_job(
            project_id=project.id,
            kind="gen_scene_asset"
        )

        # 2. 投递任务
        await session.commit()
        from app.config import get_settings
        if get_settings().celery_task_always_eager:
            from app.tasks.ai.extract_scenes import _run as run_extract
            await run_extract(job.id, project.id)
        else:
            try:
                extract_scenes.delay(job.id, project.id)
            except Exception as e:
                logger.exception(f"Failed to dispatch extract_scenes task: {e}")
                async with session.begin_nested():
                    await update_job_progress(session, job.id, status="failed", error_msg=f"任务分发失败: {str(e)}")
                await session.commit()

        return job.id
