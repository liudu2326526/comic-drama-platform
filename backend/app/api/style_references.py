from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import Envelope
from app.deps import get_db
from app.domain.schemas.style_reference import StyleReferenceJobAck
from app.domain.services.style_reference_service import StyleReferenceService


router = APIRouter(prefix="/projects/{project_id}", tags=["style-references"])


@router.post("/character-style-reference/generate", response_model=Envelope[StyleReferenceJobAck])
async def generate_character_style_reference(
    project_id: str = Path(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
):
    job = await StyleReferenceService(db).generate(project_id, "character")
    return Envelope.success(StyleReferenceJobAck(job_id=job.id))


@router.post("/scene-style-reference/generate", response_model=Envelope[StyleReferenceJobAck])
async def generate_scene_style_reference(
    project_id: str = Path(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
):
    job = await StyleReferenceService(db).generate(project_id, "scene")
    return Envelope.success(StyleReferenceJobAck(job_id=job.id))
