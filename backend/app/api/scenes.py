import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.envelope import Envelope
from app.api.errors import CONTENT_FILTER, ApiError
from app.deps import get_db
from app.domain.models import Project, Scene, Job
from app.domain.schemas.scene import (
    SceneOut, 
    SceneUpdate, 
    SceneGenerateRequest, 
    SceneLockRequest,
    SceneLockResponse,
    GenerateJobAck
)
from app.domain.services.scene_service import SceneService
from app.infra import get_volcano_client
from app.infra.volcano_errors import VolcanoContentFilterError
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import assert_asset_editable, update_job_progress, InvalidTransition
from app.tasks.ai.gen_scene_asset import gen_scene_asset
from app.config import get_settings

router = APIRouter(prefix="/projects/{project_id}/scenes", tags=["scenes"])
logger = logging.getLogger(__name__)

@router.get("", response_model=Envelope[list[SceneOut]])
async def list_scenes(
    project_id: str = Path(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db)
):
    scenes = await SceneService.list_by_project(db, project_id)
    out = [
        SceneOut(
            id=s.id,
            name=s.name,
            theme=s.theme,
            summary=s.summary,
            description=s.description,
            meta=[], # TODO
            locked=s.locked,
            template_id=s.template_id,
            reference_image_url=s.reference_image_url,
            usage="" # TODO: 拼装用法统计
        ) for s in scenes
    ]
    return Envelope.success(out)

@router.post("/generate", response_model=Envelope[GenerateJobAck])
async def generate_scenes(
    project_id: str = Path(..., description="项目 ID"),
    req: SceneGenerateRequest = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise ApiError(40401, "项目不存在", http_status=404)
    
    try:
        job_id = await SceneService.generate_async(db, project)
        return Envelope.success(GenerateJobAck(job_id=job_id, sub_job_ids=[]))
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)
    except Exception as e:
        logger.error(f"Generate scenes async failed: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")

@router.patch("/{sid}", response_model=Envelope[SceneOut])
async def update_scene(
    project_id: str = Path(..., description="项目 ID"),
    sid: str = Path(..., description="场景 ID"),
    req: SceneUpdate = None,
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    scene = await SceneService.get_by_id(db, sid)
    if not project or not scene or scene.project_id != project_id:
        raise ApiError(40401, "资源不存在", http_status=404)
    
    try:
        await SceneService.update(db, project, scene, req)
        await db.commit()
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)
    
    return Envelope.success(SceneOut(
        id=scene.id, name=scene.name, theme=scene.theme,
        summary=scene.summary, description=scene.description,
        meta=[], locked=scene.locked, template_id=scene.template_id,
        reference_image_url=scene.reference_image_url, usage=""
    ))

@router.post("/{sid}/lock", response_model=Envelope[SceneLockResponse])
async def lock_scene(
    project_id: str = Path(..., description="项目 ID"),
    sid: str = Path(..., description="场景 ID"),
    req: SceneLockRequest = None,
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    scene = await SceneService.get_by_id(db, sid)
    if not project or not scene or scene.project_id != project_id:
        raise ApiError(40401, "资源不存在", http_status=404)
    
    try:
        job_id = await SceneService.lock_async(db, project, scene)
        return Envelope.success(SceneLockResponse(
            job_id=job_id
        ))
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)

@router.post("/{sid}/regenerate", response_model=Envelope[GenerateJobAck])
async def regenerate_scene(
    project_id: str = Path(..., description="项目 ID"),
    sid: str = Path(..., description="场景 ID"),
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    scene = await SceneService.get_by_id(db, sid)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    assert_asset_editable(project, "scene")

    job = Job(
        project_id=project_id,
        kind="gen_scene_asset_single",
        status="queued"
    )
    db.add(job)
    await db.commit()
    
    gen_scene_asset.delay(scene.id, job.id)
    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))
