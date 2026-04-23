import json
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import Project, StoryboardShot, Job, ExportTask, Character, Scene, ShotRender, ShotVideoRender
from app.domain.schemas.project import ProjectDetail
from app.domain.schemas.prompt_profile import derive_prompt_profile_state
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
        
        # 2. 获取生成队列 (活跃中的 jobs + 最近完成的 5 条记录供前端展示/快照)
        stmt_jobs = select(Job).where(
            Job.project_id == project_id
        ).order_by(
            func.field(Job.status, "running", "queued", "failed", "succeeded", "canceled"),
            Job.created_at.desc()
        ).limit(20)
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

        # 5. 获取渲染详情供队列展示
        shot_map = {s.id: s for s in storyboards}
        generation_queue = [{
            "id": j.id,
            "kind": j.kind,
            "status": j.status,
            "progress": j.progress,
            "target_id": j.target_id,
            "payload": j.payload,
            "result": j.result,
        } for j in jobs]

        def _job_meta(item: dict, key: str) -> dict:
            value = item.get(key)
            return value if isinstance(value, dict) else {}

        def _resolved_render_id(item: dict) -> str | None:
            return _job_meta(item, "result").get("render_id") or _job_meta(item, "payload").get("render_id")

        def _resolved_video_render_id(item: dict) -> str | None:
            return _job_meta(item, "result").get("video_render_id") or _job_meta(item, "payload").get("video_render_id")
        
        queue_render_ids = [
            _resolved_render_id(item)
            for item in generation_queue
            if item.get("kind") == "render_shot"
        ]
        render_ids = list({rid for rid in [*(s.current_render_id for s in storyboards if s.current_render_id), *queue_render_ids] if rid})
        render_map = {}
        if render_ids:
            current_renders = (
                await self.session.execute(select(ShotRender).where(ShotRender.id.in_(render_ids)))
            ).scalars().all()
            render_map = {r.id: r for r in current_renders}

        queue_video_render_ids = [
            _resolved_video_render_id(item)
            for item in generation_queue
            if item.get("kind") == "render_shot_video"
        ]
        video_render_ids = list({
            vid
            for vid in [*(s.current_video_render_id for s in storyboards if getattr(s, "current_video_render_id", None)), *queue_video_render_ids]
            if vid
        })
        video_map: dict[str, ShotVideoRender] = {}
        if video_render_ids:
            current_videos = (
                await self.session.execute(select(ShotVideoRender).where(ShotVideoRender.id.in_(video_render_ids)))
            ).scalars().all()
            video_map = {r.id: r for r in current_videos}

        latest_render = None
        if video_render_ids:
            latest_render = max(
                (video_map[vid] for vid in video_render_ids if vid in video_map),
                key=lambda r: r.created_at,
                default=None,
            )
        elif render_ids:
            latest_render = max(
                (render_map[rid] for rid in render_ids if rid in render_map),
                key=lambda r: r.created_at,
                default=None,
            )
        
        # 6. 拼装进度文字
        total_shots = len(storyboards)
        done_shots = sum(1 for s in storyboards if s.status in ["succeeded", "locked"])
        progress_text = f"{done_shots} / {total_shots} 已完成" if total_shots > 0 else "0 / 0 已完成"
        
        # 角色 role 中文映射
        role_map = {"supporting": "配角", "atmosphere": "氛围"}

        def _meta_to_tags(meta: dict | None, video_style_ref: dict | None) -> list[str]:
            tags: list[str] = []
            if isinstance(meta, dict):
                tags.extend(str(v) for v in meta.get("tags", []) if v)
            if isinstance(video_style_ref, dict) and video_style_ref.get("asset_status"):
                tags.append(f"人像库:{video_style_ref['asset_status']}")
            return tags

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
            characterPromptProfile=derive_prompt_profile_state(
                project.character_prompt_profile_draft,
                project.character_prompt_profile_applied,
            ),
            scenePromptProfile=derive_prompt_profile_state(
                project.scene_prompt_profile_draft,
                project.scene_prompt_profile_applied,
            ),
            storyboards=[{
                "id": s.id,
                "idx": s.idx,
                "title": s.title,
                "description": s.description,
                "detail": s.detail,
                "tags": s.tags,
                "status": s.status,
                "duration_sec": float(s.duration_sec) if s.duration_sec is not None else None,
                "scene_id": s.scene_id,
                "current_render_id": s.current_render_id,
                "current_video_render_id": s.current_video_render_id,
                "current_video_url": build_asset_url(video_map[s.current_video_render_id].video_url) if getattr(s, "current_video_render_id", None) in video_map else None,
                "current_last_frame_url": build_asset_url(video_map[s.current_video_render_id].last_frame_url) if getattr(s, "current_video_render_id", None) in video_map else None,
                "current_video_version_no": video_map[s.current_video_render_id].version_no if getattr(s, "current_video_render_id", None) in video_map else None,
                "current_video_params_snapshot": video_map[s.current_video_render_id].params_snapshot if getattr(s, "current_video_render_id", None) in video_map else None,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            } for s in storyboards],
            characters=[{
                "role_type": "supporting" if c.role_type == "protagonist" else c.role_type,
                "id": c.id,
                "name": c.name,
                "role": role_map.get("supporting" if c.role_type == "protagonist" else c.role_type, "配角"),
                "is_protagonist": False,
                "locked": False,
                "summary": c.summary,
                "description": c.description,
                "meta": _meta_to_tags(c.meta, c.video_style_ref),
                "reference_image_url": build_asset_url(c.reference_image_url)
            } for c in chars],
            scenes=[{
                "id": s.id,
                "name": s.name,
                "theme": s.theme,
                "summary": s.summary,
                "description": s.description,
                "meta": _meta_to_tags(s.meta, s.video_style_ref),
                "locked": False,
                "template_id": s.template_id,
                "reference_image_url": build_asset_url(s.reference_image_url),
                "usage": f"场景复用 {usage_map.get(s.id, 0)} 镜头"
            } for s in scenes],
            generationProgress=progress_text,
            generationNotes={
                "input": "" if latest_render is None else json.dumps(latest_render.prompt_snapshot or {}, ensure_ascii=False, indent=2),
                "suggestion": "可从历史版本中选择当前镜头，或重试失败镜头。",
            },
            generationQueue=[
                {
                    **item,
                    "shot_id": item.get("target_id") if item.get("kind") == "render_shot" else None,
                    "render_id": (
                        _resolved_render_id(item)
                        if item.get("kind") == "render_shot"
                        else None
                    ),
                    "image_url": (
                        build_asset_url(render_map[resolved_render_id].image_url)
                        if item.get("kind") == "render_shot"
                        and (resolved_render_id := _resolved_render_id(item)) in render_map
                        else None
                    ),
                    "version_no": (
                        render_map[resolved_render_id].version_no
                        if item.get("kind") == "render_shot"
                        and (resolved_render_id := _resolved_render_id(item)) in render_map
                        else None
                    ),
                    "shot_status": (
                        shot_map[item["target_id"]].status
                        if item.get("kind") == "render_shot" and item.get("target_id") in shot_map
                        else None
                    ),
                    "error_code": (
                        render_map[resolved_render_id].error_code
                        if item.get("kind") == "render_shot"
                        and (resolved_render_id := _resolved_render_id(item)) in render_map
                        else None
                    ),
                    "error_msg": (
                        render_map[resolved_render_id].error_msg or item.get("error_msg")
                        if item.get("kind") == "render_shot"
                        and (resolved_render_id := _resolved_render_id(item)) in render_map
                        else None
                    ),
                }
                if item.get("kind") == "render_shot"
                else {
                    **item,
                    "shot_id": item.get("target_id"),
                    "video_render_id": (
                        _resolved_video_render_id(item)
                        if item.get("kind") == "render_shot_video"
                        else None
                    ),
                    "video_url": (
                        build_asset_url(video_map[resolved_video_id].video_url)
                        if item.get("kind") == "render_shot_video"
                        and (resolved_video_id := _resolved_video_render_id(item)) in video_map
                        else None
                    ),
                    "last_frame_url": (
                        build_asset_url(video_map[resolved_video_id].last_frame_url)
                        if item.get("kind") == "render_shot_video"
                        and (resolved_video_id := _resolved_video_render_id(item)) in video_map
                        else None
                    ),
                    "version_no": (
                        video_map[resolved_video_id].version_no
                        if item.get("kind") == "render_shot_video"
                        and (resolved_video_id := _resolved_video_render_id(item)) in video_map
                        else None
                    ),
                    "params_snapshot": (
                        video_map[resolved_video_id].params_snapshot
                        if item.get("kind") == "render_shot_video"
                        and (resolved_video_id := _resolved_video_render_id(item)) in video_map
                        else None
                    ),
                    "shot_status": (
                        shot_map[item["target_id"]].status
                        if item.get("kind") == "render_shot_video" and item.get("target_id") in shot_map
                        else None
                    ),
                    "error_code": (
                        video_map[resolved_video_id].error_code
                        if item.get("kind") == "render_shot_video"
                        and (resolved_video_id := _resolved_video_render_id(item)) in video_map
                        else None
                    ),
                    "error_msg": (
                        video_map[resolved_video_id].error_msg or item.get("error_msg")
                        if item.get("kind") == "render_shot_video"
                        and (resolved_video_id := _resolved_video_render_id(item)) in video_map
                        else None
                    ),
                }
                for item in generation_queue
            ],
            exportConfig=[],
            exportDuration="",
            exportTasks=[{
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "progress": e.progress
            } for e in exports]
        )
