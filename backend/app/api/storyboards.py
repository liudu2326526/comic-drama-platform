from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.envelope import ok
from app.api.errors import ApiError
from app.deps import get_db
from app.domain.services import StoryboardService, SceneService
from app.domain.schemas.storyboard import (
    StoryboardUpdate, 
    StoryboardReorderRequest, 
    StoryboardCreate,
    BindSceneRequest
)
from app.pipeline.transitions import InvalidTransition

router = APIRouter(prefix="/projects/{project_id}/storyboards", tags=["storyboards"])

@router.post("/{shot_id}/bind_scene")
async def bind_scene(
    project_id: str,
    shot_id: str,
    payload: BindSceneRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        shot, scene = await SceneService.bind_scene_to_shot(
            db, project_id, shot_id, payload.scene_id
        )
        await db.commit()
        return ok({
            "shot_id": shot.id,
            "scene_id": scene.id,
            "scene_name": scene.name
        })
    except ValueError as e:
        raise ApiError(40001, str(e))
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)

@router.get("")
async def list_storyboards(project_id: str, db: AsyncSession = Depends(get_db)):
    svc = StoryboardService(db)
    items = await svc.list_by_project(project_id)
    return ok([
        {
            "id": i.id,
            "idx": i.idx,
            "title": i.title,
            "description": i.description,
            "detail": i.detail,
            "tags": i.tags,
            "status": i.status,
            "duration_sec": float(i.duration_sec) if i.duration_sec is not None else None,
            "scene_id": i.scene_id
        } for i in items
    ])

@router.post("")
async def create_storyboard(
    project_id: str,
    payload: StoryboardCreate,
    db: AsyncSession = Depends(get_db)
):
    svc = StoryboardService(db)
    try:
        shot = await svc.create_shot(project_id, payload.model_dump())
        await db.commit()
        return ok({
            "id": shot.id,
            "idx": shot.idx,
            "title": shot.title,
            "status": shot.status
        })
    except InvalidTransition as e:
        raise ApiError(40301, str(e))

@router.post("/confirm")
async def confirm_storyboards(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    svc = StoryboardService(db)
    try:
        project = await svc.confirm(project_id)
        await db.commit()
        return ok({
            "stage": project.stage,
            "stage_raw": project.stage
        })
    except InvalidTransition as e:
        raise ApiError(40301, str(e))
    except ValueError as e:
        raise ApiError(40001, str(e))

@router.patch("/{shot_id}")
async def update_storyboard(
    project_id: str, 
    shot_id: str, 
    payload: StoryboardUpdate, 
    db: AsyncSession = Depends(get_db)
):
    svc = StoryboardService(db)
    try:
        shot = await svc.update_shot(shot_id, payload.model_dump(exclude_unset=True))
        if not shot:
            raise ApiError(40401, "分镜不存在")
        await db.commit()
        return ok({
            "id": shot.id,
            "idx": shot.idx,
            "title": shot.title,
            "status": shot.status
        })
    except InvalidTransition as e:
        raise ApiError(40301, str(e))

@router.post("/reorder")
async def reorder_storyboards(
    project_id: str, 
    payload: StoryboardReorderRequest, 
    db: AsyncSession = Depends(get_db)
):
    svc = StoryboardService(db)
    try:
        await svc.reorder(project_id, payload.ordered_ids)
        await db.commit()
        return ok({"reordered": True})
    except InvalidTransition as e:
        raise ApiError(40301, str(e))

@router.delete("/{shot_id}")
async def delete_storyboard(
    project_id: str, 
    shot_id: str, 
    db: AsyncSession = Depends(get_db)
):
    svc = StoryboardService(db)
    try:
        await svc.delete_shot(shot_id)
        await db.commit()
        return ok({"deleted": True})
    except InvalidTransition as e:
        raise ApiError(40301, str(e))
