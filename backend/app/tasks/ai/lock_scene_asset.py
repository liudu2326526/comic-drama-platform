import asyncio
import logging
from app.tasks.celery_app import celery_app
from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.domain.services.scene_service import SceneService
from app.domain.models import Scene, Project

logger = logging.getLogger(__name__)

@celery_app.task(name="ai.lock_scene_asset", queue="ai", bind=True)
def lock_scene_asset(self, job_id: str, project_id: str, scene_id: str):
    """
    异步任务: 锁定场景并推进项目阶段。
    1. 校验场景与镜头绑定
    2. 写入锁定状态
    3. 重新计算项目阶段
    """
    asyncio.run(_run(job_id, project_id, scene_id))

async def _run(job_id: str, project_id: str, scene_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await update_job_progress(session, job_id, status="running", done=0, total=3)
        await session.commit()

        project = await session.get(Project, project_id)
        scene = await session.get(Scene, scene_id)
        
        if not project or not scene:
            await update_job_progress(session, job_id, status="failed", error_msg="Project or Scene not found")
            await session.commit()
            return

        try:
            async def _on_step(done: int, label: str) -> None:
                await update_job_progress(session, job_id, done=done, total=3, status="running")
                await session.commit()

            await SceneService._lock_scene_steps(session, project, scene, on_step=_on_step)
            await session.commit()
            await update_job_progress(session, job_id, status="succeeded", done=3, total=3)
            await session.commit()
            
            logger.info(f"Project {project_id} scene {scene_id} locked successfully")
        except Exception as e:
            logger.exception(f"Error in lock_scene_asset task: {e}")
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()
