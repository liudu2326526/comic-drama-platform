import logging
from app.tasks.celery_app import celery_app
from app.infra.db import get_session_factory
from app.infra import get_volcano_client
from app.config import get_settings
from app.domain.models import Project, Scene, Job
from app.pipeline.transitions import update_job_progress
from app.tasks.ai.gen_scene_asset import gen_scene_asset
from app.tasks.async_runner import dispatch_task_group, run_async_task
from app.utils.json_utils import extract_json
from sqlalchemy import select

logger = logging.getLogger(__name__)

@celery_app.task(name="ai.extract_scenes", queue="ai", bind=True)
def extract_scenes(self, job_id: str, project_id: str):
    """
    异步任务: 从小说中提取场景并创建子任务。
    """
    run_async_task(_run(job_id, project_id))

async def _run(job_id: str, project_id: str) -> None:
    session_factory = get_session_factory()
    settings = get_settings()
    
    async with session_factory() as session:
        # 1. 获取项目信息
        project = await session.get(Project, project_id)
        if not project:
            await update_job_progress(session, job_id, status="failed", error_msg="Project not found")
            await session.commit()
            return

        await update_job_progress(session, job_id, status="running", progress=10)
        await session.commit()

        # 2. 调用 AI 提取场景
        prompt = f"请根据以下小说内容和分镜信息提取其中的核心场景。\n\n小说内容：\n{project.story}\n\n请以 JSON 数组格式返回，每个对象包含：name, theme, summary, description。"
        
        volcano_client = get_volcano_client()
        try:
            chat_result = await volcano_client.chat_completions(
                model=settings.ark_chat_model,
                messages=[{"role": "user", "content": prompt}]
            )
            content = chat_result.choices[0].message.content
            data = extract_json(content)
            
            if isinstance(data, dict):
                scene_data_list = data.get("scenes", [])
            elif isinstance(data, list):
                scene_data_list = data
            else:
                scene_data_list = []
                
            if not scene_data_list:
                await update_job_progress(session, job_id, status="failed", error_msg="未识别到场景")
                await session.commit()
                return
        except Exception as e:
            logger.exception(f"Extract scenes failed: {e}")
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()
            return

        # 3. 创建场景和子任务
        await update_job_progress(session, job_id, total=len(scene_data_list), done=0, progress=30)
        await session.commit()

        sub_tasks = []
        for data in scene_data_list:
            stmt = select(Scene).where(Scene.project_id == project_id, Scene.name == data["name"])
            scene = (await session.execute(stmt)).scalar_one_or_none()
            if not scene:
                scene = Scene(
                    project_id=project_id,
                    name=data["name"],
                    theme=data.get("theme", "default"),
                    summary=data.get("summary"),
                    description=data.get("description")
                )
                session.add(scene)
                await session.flush()
            
            child_job = Job(
                project_id=project_id,
                parent_id=job_id,
                kind="gen_scene_asset_single",
                status="queued"
            )
            session.add(child_job)
            await session.flush()
            sub_tasks.append((scene.id, child_job.id))

        await session.commit()

        # 4. 只有在事务提交后才分发任务, 避免子任务找不到 Job 行
        try:
            await dispatch_task_group(gen_scene_asset, sub_tasks)
        except Exception as exc:
            error_msg = f"dispatch failed: {exc}"
            await update_job_progress(session, job_id, status="failed", error_msg=error_msg)
            await session.commit()
            return

        logger.info(f"Project {project_id} scenes extracted, {len(scene_data_list)} sub-jobs dispatched")
