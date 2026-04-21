from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Project
from app.domain.schemas import ProjectCreate, ProjectUpdate
from app.pipeline import ProjectStageRaw, rollback_stage
from app.pipeline.states import STAGE_ZH
from app.pipeline.transitions import InvalidatedCounts


class ProjectNotFound(Exception):
    pass


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: ProjectCreate) -> Project:
        project = Project(
            name=payload.name,
            story=payload.story,
            genre=payload.genre,
            ratio=payload.ratio,
            setup_params=payload.setup_params,
        )
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def get(self, project_id: str) -> Project:
        project = await self.session.get(Project, project_id)
        if project is None:
            raise ProjectNotFound(project_id)
        return project

    async def list(self, page: int, page_size: int) -> tuple[list[Project], int]:
        total = await self.session.scalar(select(func.count(Project.id)))
        stmt = (
            select(Project)
            .order_by(Project.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return list(rows), int(total or 0)

    async def update(self, project_id: str, payload: ProjectUpdate) -> Project:
        project = await self.get(project_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        return project

    async def delete(self, project_id: str) -> None:
        project = await self.get(project_id)
        await self.session.delete(project)

    async def rollback(
        self, project_id: str, target_raw: ProjectStageRaw
    ) -> tuple[Project, str, InvalidatedCounts]:
        project = await self.get(project_id)
        from_stage = project.stage
        invalidated = await rollback_stage(self.session, project, target_raw)
        return project, from_stage, invalidated

    @staticmethod
    def stage_zh(raw: str) -> str:
        return STAGE_ZH[ProjectStageRaw(raw)]
