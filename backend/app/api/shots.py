from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import ok
from app.api.errors import ApiError
from app.config import get_settings
from app.deps import get_db
from app.domain.models import ShotRender
from app.domain.schemas import GenerateJobAck
from app.domain.schemas.shot_render import RenderDraftRead, RenderSubmitRequest, RenderVersionRead
from app.domain.services import JobService, ShotRenderService
from app.infra.asset_store import build_asset_url
from app.pipeline.transitions import InvalidTransition, mark_shot_render_failed, update_job_progress
from app.tasks.ai.render_shot import _render_shot_task, render_shot_task

router = APIRouter(prefix="/projects/{project_id}/shots", tags=["shots"])


@router.post("/{shot_id}/render-draft")
async def render_draft(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        draft = await ShotRenderService(db).build_render_draft(project_id, shot_id)
        return ok(RenderDraftRead(**draft).model_dump())
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.post("/{shot_id}/render")
async def render_one(
    project_id: str,
    shot_id: str,
    payload: RenderSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = ShotRenderService(db)
        render = await svc.create_render_version(project_id, shot_id, payload)
        job = await JobService(db).create_job(
            project_id=project_id,
            kind="render_shot",
            target_type="shot",
            target_id=shot_id,
            payload={"render_id": render.id, "shot_id": shot_id},
        )
        render_id = render.id
        job_id = job.id
        await db.commit()
        try:
            settings = get_settings()
            if settings.celery_task_always_eager:
                await _render_shot_task(shot_id, render_id, job_id)
            else:
                task = render_shot_task.delay(shot_id, render_id, job_id)
                job.celery_task_id = task.id
                await db.commit()
        except Exception as exc:
            render = await db.get(ShotRender, render_id)
            shot = await svc._get_shot(project_id, shot_id)
            if render is not None and render.status == "queued":
                mark_shot_render_failed(shot, render, error_code="dispatch_failed", error_msg=f"dispatch failed: {exc}")
            await update_job_progress(db, job_id, status="failed", error_msg=f"dispatch failed: {exc}")
            await db.commit()
            raise
        return ok(GenerateJobAck(job_id=job_id, sub_job_ids=[]).model_dump())
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.get("/{shot_id}/renders")
async def list_renders(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    svc = ShotRenderService(db)
    shot = await svc._get_shot(project_id, shot_id)
    renders = await svc.list_renders(project_id, shot_id)
    return ok([
        RenderVersionRead(
            id=item.id,
            shot_id=item.shot_id,
            version_no=item.version_no,
            status=item.status,
            prompt_snapshot=item.prompt_snapshot,
            image_url=build_asset_url(item.image_url),
            provider_task_id=item.provider_task_id,
            error_code=item.error_code,
            error_msg=item.error_msg,
            created_at=item.created_at,
            finished_at=item.finished_at,
            is_current=item.id == shot.current_render_id,
        ).model_dump()
        for item in renders
    ])


@router.post("/{shot_id}/renders/{render_id}/select")
async def select_render(project_id: str, shot_id: str, render_id: str, db: AsyncSession = Depends(get_db)):
    try:
        shot = await ShotRenderService(db).select_render(project_id, shot_id, render_id)
        await db.commit()
        return ok({"shot_id": shot.id, "current_render_id": shot.current_render_id, "status": shot.status})
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.post("/{shot_id}/lock")
async def lock_shot(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        shot = await ShotRenderService(db).lock_shot(project_id, shot_id)
        await db.commit()
        return ok({"shot_id": shot.id, "status": shot.status, "current_render_id": shot.current_render_id})
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)
