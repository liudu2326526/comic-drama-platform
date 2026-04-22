import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.envelope import Envelope
from app.api.errors import CONTENT_FILTER
from app.deps import get_db
from app.domain.models import Project, Scene, Job
from app.domain.schemas.scene import (
    SceneOut, 
    SceneUpdate, 
    SceneGenerateRequest, 
    SceneLockRequest,
    GenerateJobAck
)
from app.domain.services.scene_service import SceneService
from app.infra import get_volcano_client
from app.infra.volcano_errors import VolcanoContentFilterError
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import assert_asset_editable, update_job_progress
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
    settings = get_settings()
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if ProjectStageRaw(project.stage) != ProjectStageRaw.CHARACTERS_LOCKED:
        raise HTTPException(status_code=400, detail="项目阶段不支持生成场景")

    prompt = f"请根据以下小说内容和分镜信息提取其中的核心场景。\n\n小说内容：\n{project.story}\n\n请以 JSON 数组格式返回，每个对象包含：name, theme, summary, description。"
    
    volcano_client = get_volcano_client()
    try:
        chat_result = await volcano_client.chat_completions(
            model=settings.ark_chat_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = chat_result.choices[0].message.content
        scene_data_list = json.loads(content).get("scenes", [])
        if not scene_data_list:
            raise HTTPException(status_code=422, detail={"code": 40001, "message": "未识别到场景"})
    except VolcanoContentFilterError:
        raise HTTPException(status_code=422, detail={"code": CONTENT_FILTER, "message": "AI 内容违规"})
    except Exception as e:
        logger.error(f"Generate scenes failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI 生成失败: {e}")

    main_job = Job(
        project_id=project_id,
        kind="gen_scene_asset",
        status="running",
        total=len(scene_data_list),
        done=0
    )
    db.add(main_job)
    await db.flush()

    sub_job_ids = []
    for data in scene_data_list:
        stmt = select(Scene).where(Scene.project_id == project_id, Scene.name == data["name"])
        scene = (await db.execute(stmt)).scalar_one_or_none()
        if not scene:
            scene = Scene(
                project_id=project_id,
                name=data["name"],
                theme=data.get("theme", "default"),
                summary=data.get("summary"),
                description=data.get("description")
            )
            db.add(scene)
            await db.flush()
        
        child_job = Job(
            project_id=project_id,
            parent_id=main_job.id,
            kind="gen_scene_asset_single",
            status="queued"
        )
        db.add(child_job)
        await db.flush()
        sub_job_ids.append(child_job.id)

        gen_scene_asset.delay(scene.id, child_job.id)

    await db.commit()
    return Envelope.success(GenerateJobAck(job_id=main_job.id, sub_job_ids=sub_job_ids))

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
        raise HTTPException(status_code=404, detail="资源不存在")
    
    await SceneService.update(db, project, scene, req)
    await db.commit()
    return Envelope.success(SceneOut(
        id=scene.id, name=scene.name, theme=scene.theme,
        summary=scene.summary, description=scene.description,
        meta=[], locked=scene.locked, template_id=scene.template_id,
        reference_image_url=scene.reference_image_url, usage=""
    ))

@router.post("/{sid}/lock", response_model=Envelope[dict])
async def lock_scene(
    project_id: str = Path(..., description="项目 ID"),
    sid: str = Path(..., description="场景 ID"),
    req: SceneLockRequest = None,
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    scene = await SceneService.get_by_id(db, sid)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    await SceneService.lock(db, project, scene)
    await db.commit()
    return Envelope.success({"id": scene.id, "locked": True})

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
