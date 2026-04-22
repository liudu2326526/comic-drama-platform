import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.getcwd())

from app.infra.db import get_session_factory
from app.domain.models import Project
from sqlalchemy import select

async def main():
    factory = get_session_factory()
    async with factory() as s:
        stmt = select(Project).where(Project.stage == "storyboard_ready").limit(1)
        res = await s.execute(stmt)
        p = res.scalar()
        if p:
            print(p.id)
        else:
            print("none")

if __name__ == "__main__":
    asyncio.run(main())
