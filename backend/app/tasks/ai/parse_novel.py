import asyncio
import json
import logging

from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.domain.models import Project
from app.pipeline.transitions import is_job_canceled, update_job_progress
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def normalize_parsed_genre(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:64]


async def _parse_novel_task(project_id: str, job_id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            if await is_job_canceled(session, job_id):
                return
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

            # 3. 调用 AI 解析
            client = get_volcano_client()
            prompt = f"""请解析以下小说内容并返回 JSON 格式的分析结果。
要求严格遵守以下 JSON 结构：
{{
  "summary": "一句话故事梗概",
  "overview": "详细的故事背景与情节概述",
  "parsed_stats": ["角色: N", "场景: M", "预计时长: Ts"],
  "suggested_shots": 12,
  "genre": "从小说正文识别出的短题材标签,例如 现代末世、都市悬疑、科幻悬疑、古风权谋"
}}

要求：
- genre 必须只依据小说正文判断,不要沿用任何已有项目字段。
- genre 使用正向题材标签,不要通过禁止词或负面约束表达。

小说内容：
{project.story}"""

            messages = [
                {"role": "system", "content": "你是一个小说解析专家，只返回纯 JSON 内容，不包含任何解释。"},
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
            if await is_job_canceled(session, job_id):
                return
            data = extract_json(content_str)

            # 4. 更新项目
            project.summary = data.get("summary")
            project.parsed_stats = data.get("parsed_stats")
            project.overview = data.get("overview")
            project.suggested_shots = data.get("suggested_shots")
            parsed_genre = normalize_parsed_genre(data.get("genre"))
            if parsed_genre:
                project.genre = parsed_genre
            
            # 5. 更新 Job 为成功
            await update_job_progress(session, job_id, status="succeeded", progress=100)
            await session.commit()

            # 6. 链式触发分镜生成
            from app.domain.services.job_service import JobService
            from app.tasks.ai.gen_storyboard import gen_storyboard
            
            job_svc = JobService(session)
            gen_job = await job_svc.create_job(project_id, kind="gen_storyboard")
            await session.commit()

            logger.info(f"Project {project_id} parsed successfully, triggering gen_storyboard: {gen_job.id}")
            # 注意: ALWAYS_EAGER 下这会同步执行
            from app.config import get_settings
            if get_settings().celery_task_always_eager:
                # 在 eager 模式下, 我们直接运行协程体, 避免 loop 冲突
                from app.tasks.ai.gen_storyboard import _gen_storyboard_task
                await _gen_storyboard_task(project_id, gen_job.id)
            else:
                gen_storyboard.delay(project_id, gen_job.id)
            
        except Exception as e:
            if await is_job_canceled(session, job_id):
                await session.rollback()
                return
            logger.exception(f"Error in parse_novel_task: {e}")
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()

@celery_app.task(name="ai.parse_novel")
def parse_novel(project_id: str, job_id: str):
    asyncio.run(_parse_novel_task(project_id, job_id))
