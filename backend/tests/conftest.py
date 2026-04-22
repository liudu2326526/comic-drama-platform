import asyncio
import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.domain.models import Base
from app.infra import db as db_module


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def run_alembic_upgrade(connection, cfg):
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncEngine:
    settings = get_settings()
    # 严禁用业务库跑测试:test_engine 会 DROP/CREATE/TRUNCATE
    assert settings.database_url_test, (
        "MYSQL_DATABASE_TEST 未设置,拒绝在业务库上跑集成测试。"
        "请在 backend/.env 中添加 MYSQL_DATABASE_TEST=<test库名> 并提前建库。"
    )
    assert settings.database_url_test != settings.database_url, (
        "MYSQL_DATABASE_TEST 与 MYSQL_DATABASE 相同,会污染业务数据,拒绝运行。"
    )
    # NullPool: 每次 checkout 建新连接、用完即关,避免跨 event-loop 复用连接导致
    # "Future attached to a different loop" 错误(pytest-asyncio session fixture 与
    # 各 test function 使用不同 event loop 实例)。
    engine = create_async_engine(
        settings.database_url_test, future=True, poolclass=NullPool
    )

    # 走 Alembic 初始化测试库
    async with engine.begin() as conn:
        # 1. 清空旧表 (drop_all 不够干净,因为 alembic_version 表不在 Base 里)
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        res = await conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in res.fetchall()]
        for table in tables:
            await conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        # 2. 执行迁移
        # Alembic command 是同步的,需要 run_sync
        config_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        cfg = Config(config_path)
        # 强制指定 script_location 避免相对路径错误
        cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
        await conn.run_sync(run_alembic_upgrade, cfg)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncSession:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine):
    # override 全局 engine / session factory 指向测试库
    db_module._engine = test_engine
    db_module._session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    from app.main import create_app

    settings = get_settings()
    # 强制在测试环境中启用 ALWAYS_EAGER
    settings.celery_task_always_eager = True
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    # 每测例结束清空所有业务表,保证隔离
    async with test_engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE `{t.name}`"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def project_factory(db_session: AsyncSession):
    from app.domain.models import Project
    from app.infra.ulid import new_id

    async def _create(**kwargs):
        data = {
            "name": f"Test Project {new_id()}",
            "story": "Once upon a time...",
            "stage": "draft",
            "genre": "fantasy",
            "ratio": "9:16",
        }
        data.update(kwargs)
        p = Project(**data)
        db_session.add(p)
        await db_session.commit()
        await db_session.refresh(p)
        return p

    return _create
