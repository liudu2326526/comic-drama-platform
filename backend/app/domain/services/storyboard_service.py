from typing import Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import StoryboardShot, Project
from app.pipeline.transitions import assert_storyboard_editable
from app.api.errors import ApiError
from app.pipeline.states import ProjectStageRaw

class StoryboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_project(self, project_id: str) -> list[StoryboardShot]:
        stmt = select(StoryboardShot).where(StoryboardShot.project_id == project_id).order_by(StoryboardShot.idx)
        return list((await self.session.scalars(stmt)).all())

    async def get(self, shot_id: str) -> Optional[StoryboardShot]:
        return await self.session.get(StoryboardShot, shot_id)

    async def create_shot(self, project_id: str, data: dict) -> StoryboardShot:
        project = await self.session.get(Project, project_id)
        if not project:
            raise ApiError(40401, "项目不存在")
        assert_storyboard_editable(project)

        # 确定 idx
        idx = data.get("idx")
        if idx is None:
            stmt = select(func.max(StoryboardShot.idx)).where(StoryboardShot.project_id == project_id)
            max_idx = (await self.session.execute(stmt)).scalar() or 0
            idx = max_idx + 1
        
        shot = StoryboardShot(
            project_id=project_id,
            idx=idx,
            title=data.get("title", ""),
            description=data.get("description", ""),
            detail=data.get("detail"),
            duration_sec=data.get("duration_sec"),
            tags=data.get("tags"),
            status="pending"
        )
        self.session.add(shot)
        return shot

    async def update_shot(self, shot_id: str, data: dict) -> Optional[StoryboardShot]:
        shot = await self.get(shot_id)
        if not shot:
            return None
        
        # 校验项目是否可编辑
        project = await self.session.get(Project, shot.project_id)
        if not project:
            raise ApiError(40401, "项目不存在")
        assert_storyboard_editable(project)
        
        for k, v in data.items():
            if hasattr(shot, k):
                setattr(shot, k, v)
        
        return shot

    async def reorder(self, project_id: str, shot_ids: list[str]) -> None:
        project = await self.session.get(Project, project_id)
        if not project:
            raise ApiError(40401, "项目不存在")
        assert_storyboard_editable(project)
        
        # 为了避免 (project_id, idx) 唯一索引冲突, 先将 idx 改为负数
        for i, sid in enumerate(shot_ids, start=1):
            await self.session.execute(
                update(StoryboardShot).where(StoryboardShot.id == sid).values(idx=-i)
            )
        
        # 再改回正数
        for i, sid in enumerate(shot_ids, start=1):
            await self.session.execute(
                update(StoryboardShot).where(StoryboardShot.id == sid).values(idx=i)
            )

    async def delete_shot(self, shot_id: str) -> None:
        shot = await self.get(shot_id)
        if not shot:
            return
        
        project = await self.session.get(Project, shot.project_id)
        if not project:
            raise ApiError(40401, "项目不存在")
        assert_storyboard_editable(project)
        
        await self.session.delete(shot)
        # 重新整理 idx
        stmt = select(StoryboardShot).where(StoryboardShot.project_id == project.id).order_by(StoryboardShot.idx)
        remaining = (await self.session.scalars(stmt)).all()
        for i, s in enumerate(remaining, start=1):
            s.idx = i

    async def confirm(self, project_id: str) -> Project:
        project = await self.session.get(Project, project_id)
        if not project:
            raise ApiError(40401, "项目不存在")
        
        if ProjectStageRaw(project.stage) != ProjectStageRaw.DRAFT:
            raise ApiError(40301, "只有草稿阶段可以确认分镜")
        
        stmt_count = select(func.count(StoryboardShot.id)).where(StoryboardShot.project_id == project_id)
        count = (await self.session.execute(stmt_count)).scalar() or 0
        if count == 0:
            raise ApiError(40001, "分镜列表不能为空")
        
        project.stage = ProjectStageRaw.STORYBOARD_READY.value
        return project
