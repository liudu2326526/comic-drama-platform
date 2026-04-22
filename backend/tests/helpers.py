
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import Project, StoryboardShot, Job
from app.infra.ulid import new_id

async def force_stage(db_session: AsyncSession, project_id: str, stage: str) -> None:
    """强制更新项目阶段"""
    await db_session.execute(
        sa.update(Project).where(Project.id == project_id).values(stage=stage)
    )
    await db_session.commit()

async def insert_storyboards(db_session: AsyncSession, project_id: str, count: int = 1) -> list[StoryboardShot]:
    """直接插入分镜数据"""
    shots = []
    for i in range(count):
        shot = StoryboardShot(
            id=new_id(),
            project_id=project_id,
            idx=i + 1,
            title=f"Shot {i + 1}",
            description="Test description",
            detail="Test detail"
        )
        db_session.add(shot)
        shots.append(shot)
    await db_session.commit()
    return shots

async def insert_job(db_session: AsyncSession, project_id: str, kind: str, target_type: str = None, target_id: str = None) -> Job:
    """直接插入异步任务数据"""
    job = Job(
        id=new_id(),
        project_id=project_id,
        kind=kind,
        status="running",
        target_type=target_type,
        target_id=target_id,
        payload={"test": True}
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job
