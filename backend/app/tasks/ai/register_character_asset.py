# backend/app/tasks/ai/register_character_asset.py
import asyncio
from app.tasks.celery_app import celery_app
from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.domain.services.character_service import CharacterService
from app.domain.models import Character, Project

@celery_app.task(name="ai.register_character_asset", queue="ai", bind=True)
def register_character_asset(self, job_id: str, project_id: str, character_id: str):
    """
    异步任务: 将主角注册到火山引擎人像库。
    1. 创建 AssetGroup (若无)
    2. 创建 Asset (基于参考图 URL)
    3. 轮询直到 Active (约 1-2 分钟)
    """
    asyncio.run(_run(job_id, project_id, character_id))

async def _run(job_id: str, project_id: str, character_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        # 1. 标记运行中
        await update_job_progress(session, job_id, status="running", done=0, total=3)
        await session.commit()
        
        try:
            # 获取上下文
            character = await session.get(Character, character_id)
            project = await session.get(Project, project_id)
            
            if not character or not project:
                await update_job_progress(session, job_id, status="failed", error_msg="Character or Project not found")
                await session.commit()
                return

            # 定义进度上报回调
            async def _on_step(done: int, label: str) -> None:
                await update_job_progress(session, job_id, done=done, total=3, status="running")
                await session.commit()

            # 2. 执行注册步骤
            await CharacterService._register_asset_steps(session, character, on_step=_on_step)
            
            # 3. 标记成功
            await update_job_progress(session, job_id, status="succeeded", done=3, total=3)
            await session.commit()
            
        except Exception as e:
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()
            raise
