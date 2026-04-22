from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.envelope import ok
from app.api.errors import ApiError
from app.deps import get_db
from app.domain.services import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = JobService(db)
    job = await svc.get_job(job_id)
    if not job:
        raise ApiError(40401, "Job 不存在")
    
    return ok({
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "done": job.done,
        "total": job.total,
        "error_msg": job.error_msg,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "payload": job.payload,
        "result": job.result
    })
