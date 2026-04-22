from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.domain.models import Character, Project
from app.domain.schemas.character import CharacterUpdate
from app.pipeline.transitions import assert_asset_editable, lock_protagonist, advance_to_characters_locked
from app.infra import get_volcano_asset_client
from app.infra.asset_store import build_asset_url


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
        character: Character, 
        as_protagonist: bool = False
    ) -> None:
        if as_protagonist:
            await lock_protagonist(session, project, character)
            # 主角锁定后尝试入库
            await CharacterService.ensure_character_asset_registered(session, character)
        else:
            character.locked = True
        
        # 检查是否可以推进 stage
        try:
            await advance_to_characters_locked(session, project)
        except Exception:
            # 允许推进失败(可能还没锁主角),不影响单次 lock 成功
            pass

    @staticmethod
    async def ensure_character_asset_registered(session: AsyncSession, character: Character) -> None:
        """确保主角已入人像库。幂等:若已入库则跳过。"""
        if not character.reference_image_url:
            return  # 图片未生成,跳过
        
        video_ref = (character.video_style_ref or {}).copy()
        if video_ref.get("asset_id"):
            return  # 已入库,跳过(幂等保护)
        
        public_url = build_asset_url(character.reference_image_url)
        if not public_url:
            return
        
        asset_client = get_volcano_asset_client()
        
        # 创建 AssetGroup(若不存在)
        if not video_ref.get("asset_group_id"):
            group = await asset_client.create_asset_group(
                name=f"char_{character.id}",
                description=f"Project {character.project_id} - {character.name}"
            )
            video_ref["asset_group_id"] = group["Id"]
        
        # 创建 Asset
        asset = await asset_client.create_asset(
            group_id=video_ref["asset_group_id"],
            url=public_url,
            name=character.name
        )
        video_ref["asset_id"] = asset["Id"]
        video_ref["asset_status"] = "Pending"
        
        # 更新数据库
        character.video_style_ref = video_ref
        await session.flush()
        
        # 轮询直到 Active (在异步环境下,这可能会阻塞,但在 API 调用中暂且这么做,
        # 更好的做法是放在 background task)
        try:
            final = await asset_client.wait_asset_active(asset["Id"], timeout=120)
            video_ref["asset_status"] = final["Status"]
            video_ref["asset_updated_at"] = datetime.now(timezone.utc).isoformat()
            character.video_style_ref = video_ref
        except Exception:
            # 轮询失败不回滚,由后续 job 或手动重试补偿
            pass
