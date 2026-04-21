from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
