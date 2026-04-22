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
            prompt = f"""请为以下小说生成 8-12 个分镜，返回 JSON 列表。
每个分镜对象必须包含：
- idx: 序号(1, 2, ...)
- title: 镜头标题
- description: 镜头画面描述
- detail: 视觉细节提示词
- duration_sec: 建议时长(秒，数字)

小说内容：
{project.story}"""

            messages = [
                {"role": "system", "content": "你是一个分镜设计专家，只返回纯 JSON 数组内容，不包含任何解释。"},
                {"role": "user", "content": prompt}
            ]
            
            from app.config import get_settings
            from app.utils.json_utils import extract_json
            settings = get_settings()
            resp = await client.chat_completions(
                model=settings.ark_chat_model, 
                messages=messages
            )
            content_str = resp.choices[0].message.content
            # 注意: 如果使用了 json_object 模式，返回的可能是 {"storyboards": [...]}
            data = extract_json(content_str)
            if isinstance(data, dict) and "storyboards" in data:
                storyboards_data = data["storyboards"]
            elif isinstance(data, list):
                storyboards_data = data
            else:
                # 尝试再次解析，或者如果 data 是 dict 但没有 storyboards 键
                storyboards_data = data if isinstance(data, list) else []

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
            
            # 5. 推进阶段
            await advance_stage(session, project, ProjectStageRaw.STORYBOARD_READY)
            
            # 6. 更新 Job 为成功
            await update_job_progress(session, job_id, status="succeeded", progress=100)
            await session.commit()
            
            logger.info(f"Project {project_id} storyboards generated successfully, advanced to storyboard_ready")
            
        except Exception as e:
            logger.exception(f"Error in gen_storyboard_task: {e}")
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()

@celery_app.task(name="ai.gen_storyboard")
def gen_storyboard(project_id: str, job_id: str):
    asyncio.run(_gen_storyboard_task(project_id, job_id))
