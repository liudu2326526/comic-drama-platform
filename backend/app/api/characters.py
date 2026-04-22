import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.envelope import Envelope
from app.api.errors import CONTENT_FILTER
from app.deps import get_db
from app.domain.models import Project, Character, Job
from app.domain.schemas.character import (
    CharacterOut, 
    CharacterUpdate, 
    CharacterGenerateRequest, 
    CharacterLockRequest,
    GenerateJobAck
)
from app.domain.services.character_service import CharacterService
from app.infra import get_volcano_client
from app.infra.volcano_errors import VolcanoContentFilterError
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import assert_asset_editable, update_job_progress
from app.tasks.ai.gen_character_asset import gen_character_asset
from app.config import get_settings

router = APIRouter(prefix="/projects/{project_id}/characters", tags=["characters"])
logger = logging.getLogger(__name__)

@router.get("", response_model=Envelope[list[CharacterOut]])
async def list_characters(
    project_id: str = Path(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db)
):
    chars = await CharacterService.list_by_project(db, project_id)
    # TODO: 拼装 meta tags 和 reference_image_url (目前先返回原始数据)
    # 真正的拼装建议放在 aggregate_service 或 CharacterOut 的 from_orm 中
    return Envelope.success([
        CharacterOut(
            id=c.id,
            name=c.name,
            role=role_map.get(c.role_type, c.role_type),
            role_type=c.role_type,
            is_protagonist=c.is_protagonist,
            locked=c.locked,
            summary=c.summary,
            description=c.description,
            meta=[], # TODO
            reference_image_url=c.reference_image_url # TODO: build_asset_url
        ) for c in chars
    ])

@router.post("/generate", response_model=Envelope[GenerateJobAck])
async def generate_characters(
    project_id: str = Path(..., description="项目 ID"),
    req: CharacterGenerateRequest = None,
    db: AsyncSession = Depends(get_db)
):
    settings = get_settings()
    # 1. 锁住项目行
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if ProjectStageRaw(project.stage) != ProjectStageRaw.STORYBOARD_READY:
        raise HTTPException(status_code=400, detail="项目阶段不支持生成角色")

    # 2. 调用 AI 提取角色
    # 构造 prompt
    prompt = f"请根据以下小说内容提取其中的主要角色、关键配角和氛围配角。\n\n小说内容：\n{project.story}\n\n请以 JSON 数组格式返回，每个对象包含：name, role_type(protagonist/supporting/atmosphere), summary, description。"
    
    volcano_client = get_volcano_client()
    try:
        chat_result = await volcano_client.chat_completions(
            model=settings.ark_chat_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = chat_result.choices[0].message.content
        char_data_list = json.loads(content).get("characters", [])
        if not char_data_list:
            raise HTTPException(status_code=422, detail={"code": 40001, "message": "未识别到角色"})
    except VolcanoContentFilterError:
        raise HTTPException(status_code=422, detail={"code": CONTENT_FILTER, "message": "AI 内容违规"})
    except Exception as e:
        logger.error(f"Generate characters failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI 生成失败: {e}")

    # 3. 创建主 Job
    main_job = Job(
        project_id=project_id,
        kind="gen_character_asset",
        status="running",
        total=len(char_data_list),
        done=0
    )
    db.add(main_job)
    await db.flush()

    # 4. 幂等创建 Character 并分发任务
    sub_job_ids = []
    for data in char_data_list:
        # find or create
        stmt = select(Character).where(Character.project_id == project_id, Character.name == data["name"])
        char = (await db.execute(stmt)).scalar_one_or_none()
        if not char:
            char = Character(
                project_id=project_id,
                name=data["name"],
                role_type=data.get("role_type", "supporting"),
                summary=data.get("summary"),
                description=data.get("description")
            )
            db.add(char)
            await db.flush()
        
        # 创建子 job
        child_job = Job(
            project_id=project_id,
            parent_id=main_job.id,
            kind="gen_character_asset_single",
            status="queued"
        )
        db.add(child_job)
        await db.flush()
        sub_job_ids.append(child_job.id)

        # 异步分发
        gen_character_asset.delay(char.id, child_job.id)

    await db.commit()
    return Envelope.success(GenerateJobAck(job_id=main_job.id, sub_job_ids=sub_job_ids))

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
        raise HTTPException(status_code=404, detail="资源不存在")
    
    await CharacterService.update(db, project, char, req)
    await db.commit()
    return Envelope.success(CharacterOut(
        id=char.id, name=char.name, role=char.role_type, role_type=char.role_type,
        is_protagonist=char.is_protagonist, locked=char.locked,
        summary=char.summary, description=char.description,
        meta=[], reference_image_url=char.reference_image_url
    ))

@router.post("/{cid}/lock", response_model=Envelope[dict])
async def lock_character(
    project_id: str = Path(..., description="项目 ID"),
    cid: str = Path(..., description="角色 ID"),
    req: CharacterLockRequest = None,
    db: AsyncSession = Depends(get_db)
):
    project = await db.get(Project, project_id)
    char = await CharacterService.get_by_id(db, cid)
    if not project or not char or char.project_id != project_id:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    await CharacterService.lock(db, project, char, req.as_protagonist if req else False)
    await db.commit()
    return Envelope.success({"id": char.id, "locked": True, "is_protagonist": char.is_protagonist})

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
