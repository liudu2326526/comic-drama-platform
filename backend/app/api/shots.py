from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import ok
from app.api.errors import ApiError
from app.config import get_settings
from app.deps import get_db
from app.domain.models import ShotRender
from app.domain.schemas import (
    GenerateJobAck,
    ReferenceAssetCreate,
    ShotDraftRead,
    ShotVideoSubmitRequest,
    ShotVideoVersionRead,
)
from app.domain.schemas.shot_render import RenderSubmitRequest, RenderVersionRead
from app.domain.services import JobService, ShotDraftService, ShotReferenceService, ShotRenderService, ShotVideoService
from app.infra.asset_store import build_asset_url
from app.pipeline.transitions import InvalidTransition, mark_shot_render_failed, update_job_progress
from app.tasks.ai.gen_shot_draft import _gen_shot_draft_task, gen_shot_draft
from app.tasks.ai.render_shot import _render_shot_task, render_shot_task
from app.tasks.video.render_shot_video import _render_shot_video_task, render_shot_video_task

router = APIRouter(prefix="/projects/{project_id}/shots", tags=["shots"])


@router.get("/{shot_id}/reference-candidates")
async def list_reference_candidates(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    svc = ShotReferenceService(db)
    items = await svc.list_candidates(project_id, shot_id)
    return ok([item.model_dump(mode="json") for item in items])


@router.post("/{shot_id}/reference-assets")
async def create_reference_asset(
    project_id: str,
    shot_id: str,
    payload: ReferenceAssetCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        await ShotReferenceService(db)._get_shot(project_id, shot_id)
        item = await ShotReferenceService(db).create_manual_asset(project_id, payload)
        await db.commit()
        return ok(item.model_dump(mode="json"))
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)


@router.post("/{shot_id}/render-draft")
async def render_draft(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        svc = ShotDraftService(db)
        await svc.ensure_draft_renderable(project_id, shot_id)
        await svc.ensure_no_active_draft_job(project_id, shot_id)
        job = await JobService(db).create_job(
            project_id=project_id,
            kind="gen_shot_draft",
            target_type="shot",
            target_id=shot_id,
            payload={"shot_id": shot_id},
        )
        job_id = job.id
        await db.commit()
        try:
            settings = get_settings()
            if settings.celery_task_always_eager:
                await _gen_shot_draft_task(project_id, shot_id, job_id)
            else:
                task = gen_shot_draft.delay(project_id, shot_id, job_id)
                job.celery_task_id = task.id
                await db.commit()
        except Exception as exc:
            await update_job_progress(db, job_id, status="failed", error_msg=f"dispatch failed: {exc}")
            await db.commit()
            raise
        return ok(GenerateJobAck(job_id=job_id, sub_job_ids=[]).model_dump())
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.get("/{shot_id}/render-draft")
async def get_render_draft(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        draft = await ShotDraftService(db).get_latest_draft(project_id, shot_id)
        if draft is None:
            return ok(None)
        return ok(
            ShotDraftRead(
                id=draft.id,
                shot_id=draft.shot_id,
                version_no=draft.version_no,
                prompt=draft.prompt,
                references=draft.references_snapshot or [],
                optimizer_snapshot=draft.optimizer_snapshot,
                created_at=draft.created_at,
            ).model_dump()
        )
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)


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


@router.post("/{shot_id}/video")
async def generate_video(
    project_id: str,
    shot_id: str,
    payload: ShotVideoSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = ShotVideoService(db)
        video = await svc.create_video_version(
            project_id,
            shot_id,
            prompt=payload.prompt,
            references=payload.references,
            reference_mentions=payload.reference_mentions,
            duration=payload.duration,
            resolution=payload.resolution,
            model_type=payload.model_type,
            generate_audio=payload.generate_audio,
            reference_audio_url=payload.reference_audio_url,
        )
        job = await JobService(db).create_job(
            project_id=project_id,
            kind="render_shot_video",
            target_type="shot",
            target_id=shot_id,
            payload={"shot_id": shot_id, "video_render_id": video.id},
        )
        video_id = video.id
        job_id = job.id
        await db.commit()
        try:
            settings = get_settings()
            if settings.celery_task_always_eager:
                await _render_shot_video_task(shot_id, video_id, job_id)
            else:
                task = render_shot_video_task.delay(shot_id, video_id, job_id)
                job.celery_task_id = task.id
                await db.commit()
        except Exception as exc:
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


@router.get("/{shot_id}/videos")
async def list_videos(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    svc = ShotVideoService(db)
    shot = await svc._get_shot(project_id, shot_id)
    videos = await svc.list_videos(project_id, shot_id)
    return ok([
        ShotVideoVersionRead(
            id=item.id,
            shot_id=item.shot_id,
            version_no=item.version_no,
            status=item.status,
            prompt_snapshot=item.prompt_snapshot,
            params_snapshot=item.params_snapshot,
            video_url=build_asset_url(item.video_url),
            last_frame_url=build_asset_url(item.last_frame_url),
            provider_task_id=item.provider_task_id,
            error_code=item.error_code,
            error_msg=item.error_msg,
            created_at=item.created_at,
            finished_at=item.finished_at,
            is_current=item.id == shot.current_video_render_id,
        ).model_dump()
        for item in videos
    ])


@router.post("/{shot_id}/videos/{video_id}/select")
async def select_video(project_id: str, shot_id: str, video_id: str, db: AsyncSession = Depends(get_db)):
    try:
        shot = await ShotVideoService(db).select_video(project_id, shot_id, video_id)
        await db.commit()
        return ok({"shot_id": shot.id, "current_video_render_id": shot.current_video_render_id, "status": shot.status})
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.post("/{shot_id}/lock")
async def lock_shot(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        video_service = ShotVideoService(db)
        shot = await video_service._get_shot(project_id, shot_id)
        if shot.current_video_render_id:
            shot = await video_service.lock_shot(project_id, shot_id)
        else:
            shot = await ShotRenderService(db).lock_shot(project_id, shot_id)
        await db.commit()
        return ok(
            {
                "shot_id": shot.id,
                "status": shot.status,
                "current_render_id": shot.current_render_id,
                "current_video_render_id": shot.current_video_render_id,
            }
        )
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)
