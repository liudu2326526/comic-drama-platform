from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import Project, StoryboardShot, Job, ExportTask, Character, Scene
from app.domain.schemas.project import ProjectDetail
from app.pipeline.states import STAGE_ZH, ProjectStageRaw
from app.infra.asset_store import build_asset_url

from app.api.errors import ApiError

class AggregateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_project_detail(self, project_id: str) -> ProjectDetail:
        project = await self.session.get(Project, project_id)
        if not project:
            raise ApiError(40401, "项目不存在")
        
        # 1. 获取分镜
        stmt_storyboards = select(StoryboardShot).where(StoryboardShot.project_id == project_id).order_by(StoryboardShot.idx)
        storyboards = (await self.session.scalars(stmt_storyboards)).all()
        
        # 2. 获取生成队列 (正在运行的 jobs)
        stmt_jobs = select(Job).where(
            Job.project_id == project_id,
            Job.status.in_(["queued", "running"])
        ).order_by(Job.created_at.desc())
        jobs = (await self.session.scalars(stmt_jobs)).all()
        
        # 3. 获取角色和场景
        stmt_chars = select(Character).where(Character.project_id == project_id).order_by(Character.created_at)
        chars = (await self.session.scalars(stmt_chars)).all()
        
        stmt_scenes = select(Scene).where(Scene.project_id == project_id).order_by(Scene.created_at)
        scenes = (await self.session.scalars(stmt_scenes)).all()

        # 获取场景复用统计
        stmt_usage = select(StoryboardShot.scene_id, func.count(StoryboardShot.id)).where(
            StoryboardShot.project_id == project_id,
            StoryboardShot.scene_id.is_not(None)
        ).group_by(StoryboardShot.scene_id)
        usage_map = dict((await self.session.execute(stmt_usage)).all())
        
        # 4. 获取导出任务
        stmt_exports = select(ExportTask).where(ExportTask.project_id == project_id).order_by(ExportTask.created_at.desc())
        exports = (await self.session.scalars(stmt_exports)).all()
        
        # 5. 拼装进度文字
        total_shots = len(storyboards)
        done_shots = sum(1 for s in storyboards if s.status in ["succeeded", "locked"])
        progress_text = f"{done_shots} / {total_shots} 已完成" if total_shots > 0 else "0 / 0 已完成"
        
        # 角色 role 中文映射
        role_map = {"protagonist": "主角", "supporting": "配角", "atmosphere": "氛围"}

        return ProjectDetail(
            id=project.id,
            name=project.name,
            stage=STAGE_ZH[ProjectStageRaw(project.stage)],
            stage_raw=project.stage,
            genre=project.genre,
            ratio=f"{project.ratio} 竖屏",
            suggestedShots=f"建议镜头数 {project.suggested_shots}" if project.suggested_shots else "",
            story=project.story,
            summary=project.summary or "",
            parsedStats=project.parsed_stats or [],
            setupParams=project.setup_params or [],
            projectOverview=project.overview or "",
            storyboards=[{
                "id": s.id,
                "idx": s.idx,
                "title": s.title,
                "description": s.description,
                "detail": s.detail,
                "tags": s.tags,
                "status": s.status,
                "duration_sec": float(s.duration_sec) if s.duration_sec is not None else None,
                "scene_id": s.scene_id
            } for s in storyboards],
            characters=[{
                "id": c.id,
                "name": c.name,
                "role": role_map.get(c.role_type, c.role_type),
                "role_type": c.role_type,
                "is_protagonist": c.is_protagonist,
                "locked": c.locked,
                "summary": c.summary,
                "description": c.description,
                "meta": [], # TODO: 摘要化 meta
                "reference_image_url": build_asset_url(c.reference_image_url)
            } for c in chars],
            scenes=[{
                "id": s.id,
                "name": s.name,
                "theme": s.theme,
                "summary": s.summary,
                "description": s.description,
                "meta": [], # TODO: 摘要化 meta
                "locked": s.locked,
                "template_id": s.template_id,
                "reference_image_url": build_asset_url(s.reference_image_url),
                "usage": f"场景复用 {usage_map.get(s.id, 0)} 镜头"
            } for s in scenes],
            generationProgress=progress_text,
            generationNotes={"input": "", "suggestion": ""},
            generationQueue=[{
                "id": j.id,
                "kind": j.kind,
                "status": j.status,
                "progress": j.progress
            } for j in jobs],
            exportConfig=[],
            exportDuration="",
            exportTasks=[{
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "progress": e.progress
            } for e in exports]
        )
