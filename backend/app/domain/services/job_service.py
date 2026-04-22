from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import Job
from app.infra.ulid import new_id

class JobService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(
        self, 
        project_id: str, 
        kind: str, 
        target_type: str | None = None, 
        target_id: str | None = None,
        payload: dict | None = None
    ) -> Job:
        job = Job(
            id=new_id(),
            project_id=project_id,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            status="queued",
            progress=0,
            done=0,
            payload=payload
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: str) -> Job | None:
        return await self.session.get(Job, job_id)
