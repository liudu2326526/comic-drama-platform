from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import ok
from app.api.errors import ApiError
from app.deps import get_db
from app.domain.schemas import (
    InvalidatedSummary,
    ProjectCreate,
    ProjectDetail,
    ProjectRollbackRequest,
    ProjectRollbackResponse,
    ProjectSummary,
    ProjectUpdate,
)
from app.domain.services import ProjectService, JobService, AggregateService
from app.tasks.ai.parse_novel import parse_novel
from app.pipeline import ProjectStageRaw

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_summary(p) -> ProjectSummary:
    return ProjectSummary(
        id=p.id,
        name=p.name,
        stage=ProjectService.stage_zh(p.stage),
        stage_raw=p.stage,
        genre=p.genre,
        ratio=p.ratio,
        storyboard_count=0,
        character_count=0,
        scene_count=0,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def _to_detail(db: AsyncSession, p) -> ProjectDetail:
    agg_svc = AggregateService(db)
    return await agg_svc.get_project_detail(p.id)


@router.post("", status_code=200)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.create(payload)
    return ok({"id": project.id, "stage": project.stage, "created_at": project.created_at})


@router.get("")
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectService(db)
    items, total = await svc.list(page, page_size)
    return ok({
        "items": [_to_summary(p).model_dump() for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.get(project_id)
    detail = await _to_detail(db, project)
    return ok(detail.model_dump())


@router.patch("/{project_id}")
async def update_project(
    project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    svc = ProjectService(db)
    project = await svc.update(project_id, payload)
    detail = await _to_detail(db, project)
    return ok(detail.model_dump())


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    await svc.delete(project_id)
    return ok({"deleted": True})


@router.get("/{project_id}/jobs")
async def list_project_jobs(project_id: str, db: AsyncSession = Depends(get_db)):
    from app.domain.models import Job
    from sqlalchemy import select
    stmt = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
    jobs = (await db.execute(stmt)).scalars().all()
    return ok([
        {
            "id": j.id,
            "kind": j.kind,
            "status": j.status,
            "progress": j.progress,
            "created_at": j.created_at
        } for j in jobs
    ])

@router.post("/{project_id}/parse")
async def parse_project(project_id: str, db: AsyncSession = Depends(get_db)):
    from app.config import get_settings
    project_svc = ProjectService(db)
    job_svc = JobService(db)
    
    project = await project_svc.get(project_id)
    
    # 校验 Stage (只有 draft 允许解析)
    if project.stage != ProjectStageRaw.DRAFT.value:
        raise ApiError(40301, "只有草稿阶段的项目可以解析")
    
    # 创建 Job
    job = await job_svc.create_job(project_id, kind="parse_novel")
    await db.commit()
    
    # 触发 Celery 任务
    if get_settings().celery_task_always_eager:
        from app.tasks.ai.parse_novel import _parse_novel_task
        # 在 Eager 模式下直接 await 协程, 确保同步完成且不触发 loop 冲突
        await _parse_novel_task(project_id, job.id)
        return ok({"job_id": job.id})
    else:
        task = parse_novel.delay(project_id, job.id)
        job.celery_task_id = task.id
        await db.commit()
        return ok({"job_id": job.id})


@router.post("/{project_id}/rollback")
async def rollback_project(
    project_id: str, payload: ProjectRollbackRequest, db: AsyncSession = Depends(get_db)
):
    try:
        target = ProjectStageRaw(payload.to_stage)
    except ValueError:
        raise ApiError(40001, f"非法的 to_stage 值: {payload.to_stage}", http_status=422)

    svc = ProjectService(db)
    project, from_stage, invalidated = await svc.rollback(project_id, target)
    resp = ProjectRollbackResponse(
        from_stage=from_stage,
        to_stage=project.stage,
        invalidated=InvalidatedSummary(
            shots_reset=invalidated.shots_reset,
            characters_unlocked=invalidated.characters_unlocked,
            scenes_unlocked=invalidated.scenes_unlocked,
        ),
    )
    return ok(resp.model_dump())
