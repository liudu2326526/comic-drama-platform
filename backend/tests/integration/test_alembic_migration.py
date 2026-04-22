import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text


@pytest.mark.asyncio
async def test_migration_idempotency(test_engine):
    """
    测试迁移是幂等的: 重复 upgrade head 不应报错。
    """
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
    cfg = Config(config_path)
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))

    def run_upgrade(connection):
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")

    # test_engine 已经升过一次了,这里再升一次
    async with test_engine.begin() as conn:
        await conn.run_sync(run_upgrade)

    # 检查表是否存在
    async with test_engine.connect() as conn:
        res = await conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in res.fetchall()]
        assert "projects" in tables
        assert "jobs" in tables
        assert "alembic_version" in tables
