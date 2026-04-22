from typing import Sequence, Callable, Awaitable
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.domain.models import Scene, Project, StoryboardShot
from app.domain.schemas.scene import SceneUpdate
from app.pipeline.transitions import assert_asset_editable, advance_to_scenes_locked

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
    async def lock(
        session: AsyncSession, 
        project: Project, 
        scene: Scene
    ) -> dict:
        """同步普通锁定:立即置锁 + 尝试推进 stage"""
        assert_asset_editable(project, "scene")
        scene.locked = True
        
        # 尝试推进 stage
        try:
            await advance_to_scenes_locked(session, project)
        except Exception:
            pass
            
        return {"id": scene.id, "locked": scene.locked}

    @staticmethod
    async def _lock_scene_steps(
        session: AsyncSession,
        project: Project,
        scene: Scene,
        on_step: Callable[[int, str], Awaitable[None]] | None = None,
    ) -> None:
        """1) 校验场景与镜头绑定 2) 写入锁定状态 3) 重新计算项目阶段"""
        from app.pipeline.transitions import advance_to_scenes_locked, InvalidTransition

        assert_asset_editable(project, "scene")

        if on_step:
            await on_step(0, "校验场景与镜头绑定")
        # 目前没有特别的绑定完整性校验在单个场景锁定层级, 只要满足 assert_asset_editable 即可
        
        if on_step:
            await on_step(1, "写入锁定状态")
        scene.locked = True
        await session.flush()

        if on_step:
            await on_step(2, "重新计算项目阶段")
        try:
            await advance_to_scenes_locked(session, project)
        except InvalidTransition:
            # 允许当前 scene 已锁定, 但项目仍停留在 characters_locked (因为其他场景还没锁完)
            pass

        if on_step:
            await on_step(3, "完成")

    @staticmethod
    async def lock_async(session: AsyncSession, project: Project, scene: Scene) -> str:
        """异步分支: 创建 lock_scene_asset job 并投递任务"""
        from app.tasks.ai.lock_scene_asset import lock_scene_asset
        from app.domain.services.job_service import JobService
        from app.domain.models import Job
        from app.api.errors import ApiError
        from app.pipeline.transitions import update_job_progress

        assert_asset_editable(project, "scene")

        # 查重
        stmt = select(Job).where(
            Job.project_id == project.id,
            Job.kind == "lock_scene_asset",
            Job.status.in_(["queued", "running"])
        )
        existing_jobs = (await session.execute(stmt)).scalars().all()
        for j in existing_jobs:
            if j.payload and j.payload.get("scene_id") == scene.id:
                raise ApiError(40901, "该场景锁定任务正在进行中")

        # 1. 创建 Job
        job = await JobService(session).create_job(
            project_id=project.id,
            kind="lock_scene_asset",
            payload={"scene_id": scene.id}
        )

        # 2. 投递任务
        await session.commit()
        from app.config import get_settings
        if get_settings().celery_task_always_eager:
            from app.tasks.ai.lock_scene_asset import _run as run_lock
            await run_lock(job.id, project.id, scene.id)
        else:
            try:
                lock_scene_asset.delay(job.id, project.id, scene.id)
            except Exception as e:
                logger.exception(f"Failed to dispatch lock_scene_asset task: {e}")
                async with session.begin_nested():
                    await update_job_progress(session, job.id, status="failed", error_msg=f"任务分发失败: {str(e)}")
                await session.commit()

        return job.id

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
