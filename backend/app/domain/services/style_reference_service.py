from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.domain.models import Job, Project
from app.domain.schemas.style_reference import StyleReferenceKind
from app.domain.services.job_service import JobService
from app.pipeline.transitions import assert_asset_editable, update_job_progress
from app.tasks.ai.gen_style_reference import gen_character_style_reference, gen_scene_style_reference


class StyleReferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, project_id: str, kind: StyleReferenceKind) -> Job:
        project = await self.session.get(Project, project_id)
        if not project:
            raise ApiError(40401, "项目不存在", http_status=404)

        assert_asset_editable(project, kind)
        if kind == "scene" and not (
            isinstance(project.scene_prompt_profile_applied, dict)
            and str(project.scene_prompt_profile_applied.get("prompt") or "").strip()
        ):
            raise ApiError(40901, "请先确认场景统一视觉设定后再生成场景参考图", http_status=409)
        job_kind = f"gen_{kind}_style_reference"

        existing = (
            await self.session.execute(
                select(Job).where(
                    Job.project_id == project_id,
                    Job.kind == job_kind,
                    Job.status.in_(["queued", "running"]),
                )
            )
        ).scalars().first()
        if existing:
            raise ApiError(40901, "已有风格参考图生成任务进行中", http_status=409)

        setattr(project, f"{kind}_style_reference_status", "running")
        setattr(project, f"{kind}_style_reference_error", None)
        job = await JobService(self.session).create_job(project_id=project_id, kind=job_kind)
        await self.session.commit()

        task = gen_character_style_reference if kind == "character" else gen_scene_style_reference
        try:
            async_result = task.delay(project_id, job.id)
            job.celery_task_id = getattr(async_result, "id", None)
            await self.session.commit()
        except Exception as exc:
            await update_job_progress(self.session, job.id, status="failed", error_msg=f"dispatch failed: {exc}")
            setattr(project, f"{kind}_style_reference_status", "failed")
            setattr(project, f"{kind}_style_reference_error", f"dispatch failed: {exc}")
            await self.session.commit()
            raise

        return job
