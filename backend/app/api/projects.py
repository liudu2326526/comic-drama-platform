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
from app.domain.services import ProjectService
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


def _to_detail(p) -> ProjectDetail:
    return ProjectDetail(
        id=p.id,
        name=p.name,
        stage=ProjectService.stage_zh(p.stage),
        stage_raw=p.stage,
        genre=p.genre,
        ratio=f"{p.ratio} 竖屏",
        suggestedShots=f"建议镜头数 {p.suggested_shots}" if p.suggested_shots else "",
        story=p.story,
        summary=p.summary or "",
        parsedStats=p.parsed_stats or [],
        setupParams=p.setup_params or [],
        projectOverview=p.overview or "",
    )


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
    return ok(_to_detail(project).model_dump())


@router.patch("/{project_id}")
async def update_project(
    project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    svc = ProjectService(db)
    project = await svc.update(project_id, payload)
    return ok(_to_detail(project).model_dump())


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    await svc.delete(project_id)
    return ok({"deleted": True})


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
