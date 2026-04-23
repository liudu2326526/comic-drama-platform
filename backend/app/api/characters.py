from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.envelope import Envelope
from app.api.errors import ApiError
from app.deps import get_db
from app.domain.models import Character, Job, Project
from app.domain.schemas.character import (
    CharacterGenerateRequest,
    CharacterOut,
    CharacterUpdate,
    GenerateJobAck,
)
from app.domain.services.character_service import CharacterService
from app.pipeline.transitions import InvalidTransition, advance_to_characters_locked, assert_asset_editable, update_job_progress
from app.tasks.ai.gen_character_asset import gen_character_asset

router = APIRouter(prefix="/projects/{project_id}/characters", tags=["characters"])


def _to_character_out(c: Character) -> CharacterOut:
    normalized_role = "supporting" if c.role_type == "protagonist" else c.role_type
    role_cn = {"supporting": "配角", "atmosphere": "氛围"}
    return CharacterOut(
        id=c.id,
        name=c.name,
        role=role_cn.get(normalized_role, normalized_role),
        role_type=normalized_role,
        is_protagonist=False,
        locked=False,
        summary=c.summary,
        description=c.description,
        meta=[],
        reference_image_url=c.reference_image_url,
    )

@router.get("", response_model=Envelope[list[CharacterOut]])
async def list_characters(
    project_id: str = Path(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db)
):
    chars = await CharacterService.list_by_project(db, project_id)
    return Envelope.success([_to_character_out(c) for c in chars])

@router.post("/generate", response_model=Envelope[GenerateJobAck])
async def generate_characters(
    project_id: str = Path(..., description="项目 ID"),
    req: CharacterGenerateRequest = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise ApiError(40401, "项目不存在", http_status=404)

    try:
        assert_asset_editable(project, "character")
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)

    running_stmt = select(Job).where(
        Job.project_id == project_id,
        Job.kind.in_(["extract_characters", "gen_character_asset"]),
        Job.status.in_(["queued", "running"]),
    )
    existing = (await db.execute(running_stmt)).scalars().first()
    if existing:
        raise ApiError(40901, "已有角色生成任务进行中", http_status=409)

    job = Job(
        project_id=project_id,
        kind="extract_characters",
        status="queued",
        progress=0,
        done=0,
        total=None,
    )
    db.add(job)
    await db.commit()

    from app.tasks.ai.extract_characters import extract_characters

    try:
        extract_characters.delay(project_id, job.id)
    except Exception as exc:
        await update_job_progress(
            db,
            job.id,
            status="failed",
            error_msg=f"dispatch failed: {exc}",
        )
        await db.commit()
        raise
    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))

@router.patch("/{cid}", response_model=Envelope[CharacterOut])
async def update_character(
    project_id: str = Path(..., description="项目 ID"),
    cid: str = Path(..., description="角色 ID"),
    req: CharacterUpdate = None,
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    char = await CharacterService.get_by_id(db, cid)
    if not project or not char or char.project_id != project_id:
        raise ApiError(40401, "资源不存在", http_status=404)
    
    try:
        await CharacterService.update(db, project, char, req)
        await db.commit()
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)
    
    return Envelope.success(_to_character_out(char))

@router.post("/{cid}/register_asset", response_model=Envelope[GenerateJobAck])
async def register_character_asset(
    project_id: str = Path(..., description="项目 ID"),
    cid: str = Path(..., description="角色 ID"),
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    char = await CharacterService.get_by_id(db, cid)
    if not project or not char or char.project_id != project_id:
        raise ApiError(40401, "资源不存在", http_status=404)
    
    try:
        body = await CharacterService.register_asset_async(db, project, char)
        return Envelope.success(GenerateJobAck(**body))
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)
    except ApiError:
        raise


@router.post("/confirm", response_model=Envelope[dict])
async def confirm_characters_stage(
    project_id: str = Path(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise ApiError(40401, "项目不存在", http_status=404)

    try:
        await advance_to_characters_locked(db, project)
        await db.commit()
        return Envelope.success({"stage": project.stage, "stage_raw": project.stage})
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)

@router.post("/{cid}/regenerate", response_model=Envelope[GenerateJobAck])
async def regenerate_character(
    project_id: str = Path(..., description="项目 ID"),
    cid: str = Path(..., description="角色 ID"),
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    char = await CharacterService.get_by_id(db, cid)
    if not project or not char or char.project_id != project_id:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    assert_asset_editable(project, "character")

    job = Job(
        project_id=project_id,
        kind="gen_character_asset_single",
        status="queued"
    )
    db.add(job)
    await db.commit()
    
    gen_character_asset.delay(char.id, job.id)
    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))
