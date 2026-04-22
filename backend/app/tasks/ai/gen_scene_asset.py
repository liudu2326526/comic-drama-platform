import asyncio
import logging
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.infra.asset_store import persist_generated_asset
from app.domain.models import Scene, Job
from app.pipeline.transitions import update_job_progress
from app.tasks.celery_app import celery_app
from app.config import get_settings

logger = logging.getLogger(__name__)

async def _gen_scene_asset_task(scene_id: str, job_id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await update_job_progress(session, job_id, status="running", progress=10)
            await session.commit()

            scene = await session.get(Scene, scene_id)
            if not scene:
                logger.error(f"Scene {scene_id} not found")
                await update_job_progress(session, job_id, status="failed", error_msg="Scene not found")
                await session.commit()
                return

            settings = get_settings()
            client = get_volcano_client()
            
            # 1. 调用 AI 生成图片
            # 构造 prompt
            prompt = f"场景名称：{scene.name}\n场景主题：{scene.theme}\n场景简介：{scene.summary}\n场景详述：{scene.description}\n\n请生成该场景的写实环境图。"
            
            gen_resp = await client.image_generations(
                model=settings.ark_image_model,
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            temp_url = gen_resp.data[0].url
            
            await update_job_progress(session, job_id, progress=50)
            await session.commit()

            # 2. 持久化到 OBS
            object_key = await persist_generated_asset(
                url=temp_url,
                project_id=scene.project_id,
                kind="scene",
                ext="png"
            )
            
            # 3. 更新场景
            scene.reference_image_url = object_key
            
            # 4. 更新 Job
            await update_job_progress(session, job_id, status="succeeded", progress=100)
            
            # 5. 如果有 parent_job, 检查进度
            parent_id = (await session.get(Job, job_id)).parent_id
            if parent_id:
                from sqlalchemy import select, func
                stmt = select(func.count(Job.id)).where(Job.parent_id == parent_id, Job.status == "succeeded")
                done_count = (await session.execute(stmt)).scalar() or 0
                
                parent_job = await session.get(Job, parent_id)
                if parent_job:
                    await update_job_progress(session, parent_id, done=done_count)
                    if done_count >= parent_job.total:
                        await update_job_progress(session, parent_id, status="succeeded", progress=100)

            await session.commit()
            logger.info(f"Scene {scene_id} asset generated and persisted: {object_key}")

        except Exception as e:
            logger.exception(f"Error in gen_scene_asset_task: {e}")
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()

@celery_app.task(name="app.tasks.ai.gen_scene_asset.gen_scene_asset")
def gen_scene_asset(scene_id: str, job_id: str):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_gen_scene_asset_task(scene_id, job_id))
    except RuntimeError:
        asyncio.run(_gen_scene_asset_task(scene_id, job_id))
