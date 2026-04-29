import asyncio
import json
import logging

from app.config import get_settings
from app.domain.models import Job, Project
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.pipeline.transitions import is_job_canceled, update_job_progress
from app.tasks.celery_app import celery_app
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


def build_character_prompt_profile_messages(project: Project) -> list[dict[str, str]]:
    system_prompt = (
        "你是漫剧项目的视觉设定师。"
        "请只返回 JSON 对象，字段固定为 prompt。"
        "prompt 必须是一段中文自然语言，只服务于角色参考图和角色形象统一，不服务于场景图。"
        "显式覆盖以下 6 个维度："
        "portrait_layout、visual_style、palette_lighting、line_rendering、"
        "character_rules、negative_rules。"
        "portrait_layout 必须写明 9:16竖屏、白底或极简浅色背景、单人全身设定图。"
        "不要写入任何环境描写、世界观事件、地点、建筑、天气、场景道具、怪物、群众或剧情动作。"
        "不要返回 markdown，不要返回解释，不要省略字段语义。"
    )
    project_context = {
        "name": project.name,
        "genre": project.genre,
        "ratio": project.ratio,
        "story": project.story,
        "summary": project.summary,
        "overview": project.overview,
        "setup_params": project.setup_params or [],
    }
    user_prompt = (
        "请基于以下项目上下文，生成一段适合所有角色参考图复用的统一视觉设定。\n"
        f"{json.dumps(project_context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    settings = get_settings()
    async with session_factory() as session:
        try:
            if await is_job_canceled(session, job_id):
                return
            await update_job_progress(session, job_id, status="running", progress=10)
            await session.commit()

            project = await session.get(Project, project_id)
            if project is None:
                await update_job_progress(session, job_id, status="failed", error_msg="Project not found")
                await session.commit()
                return

            response = await get_volcano_client().chat_completions(
                model=settings.ark_chat_model,
                messages=build_character_prompt_profile_messages(project),
            )
            if await is_job_canceled(session, job_id):
                return
            content = response.choices[0].message.content
            payload = {"prompt": extract_json(content)["prompt"].strip(), "source": "ai"}
            project.character_prompt_profile_draft = payload

            job = await session.get(Job, job_id)
            if job is not None:
                job.result = {"profile_kind": "character"}

            await update_job_progress(session, job_id, status="succeeded", progress=100)
            await session.commit()
        except Exception as exc:
            if await is_job_canceled(session, job_id):
                await session.rollback()
                return
            logger.exception("generate character prompt profile failed: %s", exc)
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()


@celery_app.task(name="ai.gen_character_prompt_profile", queue="ai")
def gen_character_prompt_profile(project_id: str, job_id: str) -> None:
    asyncio.run(_run(project_id, job_id))
