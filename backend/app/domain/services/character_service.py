from typing import Sequence, Callable, Awaitable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import logging

from app.domain.models import Character, Project
from app.domain.schemas.character import CharacterUpdate
from app.pipeline.transitions import assert_asset_editable, lock_protagonist, advance_to_characters_locked
from app.infra import get_volcano_asset_client
from app.infra.asset_store import build_asset_url

logger = logging.getLogger(__name__)


class CharacterService:
    @staticmethod
    async def list_by_project(session: AsyncSession, project_id: str) -> Sequence[Character]:
        stmt = select(Character).where(Character.project_id == project_id).order_by(Character.created_at)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, character_id: str) -> Character | None:
        return await session.get(Character, character_id)

    @staticmethod
    async def update(
        session: AsyncSession, 
        project: Project, 
        character: Character, 
        update_data: CharacterUpdate
    ) -> Character:
        assert_asset_editable(project, "character")
        
        data = update_data.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(character, key, value)
        
        return character

    @staticmethod
    async def lock(
        session: AsyncSession, 
        project: Project, 
        character: Character
    ) -> dict:
        """同步普通锁定(as_protagonist 始终为 False): 立即置锁 + 尝试推进 stage"""
        assert_asset_editable(project, "character")
        character.locked = True
        
        # 检查是否可以推进 stage
        try:
            await advance_to_characters_locked(session, project)
        except Exception:
            pass
            
        return {
            "id": character.id, 
            "locked": character.locked, 
            "is_protagonist": character.is_protagonist
        }

    @staticmethod
    async def lock_protagonist_async(
        session: AsyncSession, 
        project: Project, 
        character: Character
    ) -> str:
        """异步分支:同步完成 lock_protagonist(标主角)+ 投递 register_character_asset task,返回 job_id"""
        from app.tasks.ai.register_character_asset import register_character_asset
        from app.domain.services.job_service import JobService
        from app.domain.models import Job
        from app.api.errors import ApiError
        from app.pipeline.transitions import update_job_progress

        assert_asset_editable(project, "character")

        # 0. I2: 查重 (后端兜底)
        stmt = select(Job).where(
            Job.project_id == project.id,
            Job.kind == "register_character_asset",
            Job.status.in_(["queued", "running"])
        )
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            raise ApiError(40901, "已有主角锁定任务进行中")
        
        # 1. 同步标为主角 + locked=True
        await lock_protagonist(session, project, character)
        
        # 2. 创建 Job
        job = await JobService(session).create_job(
            project_id=project.id, 
            kind="register_character_asset",
            payload={"character_id": character.id}
        )
        
        # 3. 投递任务
        await session.commit()
        from app.config import get_settings
        if get_settings().celery_task_always_eager:
            from app.tasks.ai.register_character_asset import _run as run_register
            await run_register(job.id, project.id, character.id)
        else:
            try:
                register_character_asset.delay(job.id, project.id, character.id)
            except Exception as e:
                # I1: Broker 异常处理
                logger.exception(f"Failed to dispatch register_character_asset task: {e}")
                # 重新获取 session 或使用现有 session (注意 commit 后 session 可能需要处理)
                # 此处简单起见, 另起一个事务更新状态
                async with session.begin_nested():
                    await update_job_progress(session, job.id, status="failed", error_msg=f"任务分发失败: {str(e)}")
                await session.commit()
        
        return job.id

    @staticmethod
    async def _register_asset_steps(
        session: AsyncSession,
        character: Character,
        on_step: Callable[[int, str], Awaitable[None]] | None = None,
    ) -> None:
        """1) create_group(若无) 2) create_asset 3) wait_active。幂等。"""
        if not character.reference_image_url:
            return
            
        video_ref = (character.video_style_ref or {}).copy()
        if video_ref.get("asset_id") and video_ref.get("asset_status") == "Active":
            if on_step: await on_step(3, "已入库,跳过")
            return

        try:
            asset_client = get_volcano_asset_client()
        except Exception as e:
            logger.warning(f"Skip asset registration: {e}")
            return

        try:
            # Step 0: Group
            if not video_ref.get("asset_group_id"):
                if on_step: await on_step(0, "创建 AssetGroup")
                group = await asset_client.create_asset_group(
                    name=f"char_{character.id}",
                    description=f"Project {character.project_id} - {character.name}"
                )
                video_ref["asset_group_id"] = group["Id"]

            # Step 1: Asset
            if not video_ref.get("asset_id"):
                if on_step: await on_step(1, "创建 Asset")
                public_url = build_asset_url(character.reference_image_url)
                if not public_url:
                    return
                asset = await asset_client.create_asset(
                    group_id=video_ref["asset_group_id"],
                    url=public_url,
                    name=character.name
                )
                video_ref["asset_id"] = asset["Id"]
                video_ref["asset_status"] = "Pending"
                character.video_style_ref = video_ref
                await session.flush()

            # Step 2: Wait
            if video_ref.get("asset_status") != "Active":
                if on_step: await on_step(2, "等待 Active")
                final = await asset_client.wait_asset_active(video_ref["asset_id"], timeout=180)
                video_ref["asset_status"] = final["Status"]
                video_ref["asset_updated_at"] = datetime.now(timezone.utc).isoformat()
                character.video_style_ref = video_ref
                await session.flush()

            if on_step: await on_step(3, "完成")
        finally:
            close = getattr(asset_client, "aclose", None)
            if close is not None:
                await close()

    @staticmethod
    async def ensure_character_asset_registered(session: AsyncSession, character: Character) -> None:
        """保持向后兼容的旧接口。"""
        await CharacterService._register_asset_steps(session, character)
