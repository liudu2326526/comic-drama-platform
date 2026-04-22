import asyncio
import json
import logging

from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.domain.models import Project, StoryboardShot
from app.pipeline import ProjectStageRaw, advance_stage, update_job_progress
from app.pipeline.storyboard_states import StoryboardStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

async def _gen_storyboard_task(project_id: str, job_id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            # 1. 更新 Job 状态为 running
            await update_job_progress(session, job_id, status="running", progress=10)
            await session.commit()

            # 2. 获取项目信息
            project = await session.get(Project, project_id)
            if not project:
                logger.error(f"Project {project_id} not found")
                await update_job_progress(session, job_id, status="failed", error_msg="Project not found")
                await session.commit()
                return

            # 3. 调用 AI 生成分镜
            client = get_volcano_client()
            messages = [
                {"role": "system", "content": "你是一个分镜设计专家。"},
                {"role": "user", "content": f"请为以下小说生成 8-12 个分镜,返回 JSON 列表:\n\n{project.story}"}
            ]
            
            from app.config import get_settings
            settings = get_settings()
            resp = await client.chat_completions(model=settings.ark_chat_model, messages=messages)
            content_str = resp.choices[0].message.content
            storyboards_data = json.loads(content_str)

            # 4. 批量插入分镜
            # 先清理已有的分镜(如果是重跑的话,但 M2 暂不考虑复杂重跑逻辑)
            # 在 M2 计划中,gen_storyboard 是从 draft 迁移到 storyboard_ready
            
            for item in storyboards_data:
                shot = StoryboardShot(
                    project_id=project_id,
                    idx=item["idx"],
                    title=item["title"],
                    description=item["description"],
                    detail=item.get("detail", ""),
                    duration_sec=item.get("duration_sec", 5.0),
                    status=StoryboardStatus.PENDING.value
                )
                session.add(shot)
            
            # 5. 更新 Job 为成功
            await update_job_progress(session, job_id, status="succeeded", progress=100)
            await session.commit()
            
            logger.info(f"Project {project_id} storyboards generated successfully")
            
        except Exception as e:
            logger.exception(f"Error in gen_storyboard_task: {e}")
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()

@celery_app.task(name="ai.gen_storyboard")
def gen_storyboard(project_id: str, job_id: str):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_gen_storyboard_task(project_id, job_id))
    except RuntimeError:
        asyncio.run(_gen_storyboard_task(project_id, job_id))
