# Backend M1: 基础骨架与项目 CRUD + Rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭好后端项目骨架,打通 FastAPI + SQLAlchemy + Alembic + Celery + Redis + MySQL,并交付可真实运行的项目 CRUD、阶段回退(rollback)、jobs 表与健康检查;所有 AI/资产生成阶段跃迁在本里程碑均用 mock 实现,以便后续 M2 无缝替换。

**Architecture:** 按后端设计文档 §3 采用"三层 + pipeline"结构:`api/` 做薄路由、`domain/` 放 ORM+schema+service、`pipeline/` 独占状态机、`infra/` 装 DB/Redis/Celery 适配。所有状态字段写入必须经过 `pipeline.transitions`,其他层只能读。

**Tech Stack:** Python 3.11 / FastAPI 0.110+ / SQLAlchemy 2.x async (asyncmy) / Alembic / Pydantic v2 / Celery 5 / Redis 7 / MySQL 8 / pytest + pytest-asyncio / docker-compose。

**References:**
- 设计文档:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md`
- 前端契约文档:`docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §9

---

## 文件结构(M1 交付的所有文件)

**新建**:

```
backend/
├── pyproject.toml
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_init_projects_jobs.py
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── deps.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── envelope.py
│   │   ├── errors.py
│   │   ├── health.py
│   │   └── projects.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── project.py
│   │   │   └── job.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── project.py
│   │   │   └── job.py
│   │   └── services/
│   │       ├── __init__.py
│   │       └── project_service.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── states.py
│   │   └── transitions.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── celery_app.py
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── redis_client.py
│   │   └── ulid.py
│   └── utils/
│       ├── __init__.py
│       └── logger.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_ulid.py
    │   └── test_pipeline_transitions.py
    └── integration/
        ├── __init__.py
        ├── test_projects_api.py
        └── test_rollback_api.py
```

**修改**:无(M1 从零起步)

**责任**:
- `app/config.py`:Pydantic Settings,所有环境变量在此聚合
- `app/infra/db.py`:异步 engine + session factory
- `app/infra/redis_client.py`:redis 连接池(仅连通性,暂不使用)
- `app/infra/ulid.py`:ULID 生成工具
- `app/domain/models/base.py`:SQLAlchemy `DeclarativeBase` 和通用时间列 mixin
- `app/domain/models/project.py`:`projects` 表 ORM
- `app/domain/models/job.py`:`jobs` 表 ORM(M1 仅建表,不写入业务)
- `app/domain/schemas/project.py`:Pydantic 请求/响应
- `app/domain/services/project_service.py`:CRUD 业务逻辑
- `app/pipeline/states.py`:stage ENUM + 允许的跃迁矩阵
- `app/pipeline/transitions.py`:状态写入的唯一入口,含 rollback 和下游清理(M1 下游表为空,仅占位)
- `app/tasks/celery_app.py`:Celery 实例 + `queue=ai/video` + 一个 ping 任务
- `app/api/envelope.py`:统一响应信封 `{code, message, data}`
- `app/api/errors.py`:自定义异常 + 全局 handler
- `app/api/projects.py`:CRUD + `/rollback` 端点
- `app/api/health.py`:`/healthz` + `/readyz`
- `app/main.py`:FastAPI 实例装配
- `tests/conftest.py`:测试 fixtures(DB session、httpx client)

---

## 实施前提

- 已安装 Python 3.11+、MySQL 8 客户端
- **M1 不使用 docker**:MySQL 与 Redis 连接信息由用户在 `backend/.env` 中预先配置(组件式 `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` + `REDIS_HOST/PORT`),代码从组件拼 URL
- 必须提前在 MySQL 里建好 `MYSQL_DATABASE`(业务库)与 `MYSQL_DATABASE_TEST`(测试库,独立,因集成测试会 DROP/CREATE/TRUNCATE)。建议:`creative_platform` + `creative_platform_test`
- 当前 repo 根目录执行所有命令
- 所有命令**相对 repo 根目录**,除非显式 `cd backend`
- `backend/Dockerfile` 与 `backend/docker-compose.yml` 仅作为后续部署里程碑的预留文件,M1 DoD 不再要求可构建

---

## Task 1: 初始化 backend/ 与 pyproject

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`

- [ ] **Step 1: 创建目录和 pyproject.toml**

```bash
mkdir -p backend/{app/{api,domain/{models,schemas,services},pipeline,tasks,infra,utils},tests/{unit,integration},alembic/versions}
```

```toml
# backend/pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "comic-drama-backend"
version = "0.1.0"
description = "漫剧生成平台后端"
requires-python = ">=3.11"
dependencies = [
  "fastapi==0.110.0",
  "uvicorn[standard]==0.29.0",
  "sqlalchemy[asyncio]==2.0.29",
  "asyncmy==0.2.9",
  "alembic==1.13.1",
  "pydantic==2.6.4",
  "pydantic-settings==2.2.1",
  "celery==5.3.6",
  "redis==5.0.3",
  "python-ulid==2.2.0",
  "structlog==24.1.0",
  "httpx==0.27.0",
]

[project.optional-dependencies]
dev = [
  "pytest==8.1.1",
  "pytest-asyncio==0.23.6",
  "pytest-cov==4.1.0",
  "ruff==0.3.4",
  "mypy==1.9.0",
]

[tool.setuptools.packages.find]
include = ["app*"]
exclude = ["tests*", "alembic*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: .env.example 与 .gitignore**

```
# backend/.env.example
APP_ENV=dev
LOG_LEVEL=INFO

# —— MySQL(组件式,与现有 .env 约定一致)——
MYSQL_HOST=172.16.7.108
MYSQL_PORT=3308
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=creative_platform
MYSQL_DATABASE_TEST=creative_platform_test

# —— Redis ——
REDIS_HOST=172.16.7.108
REDIS_PORT=36379
REDIS_DB=0
REDIS_DB_BROKER=1
REDIS_DB_RESULT=2

# —— 其他 ——
STORAGE_ROOT=/tmp/comic_drama_assets
STATIC_BASE_URL=http://127.0.0.1/static/

VOLCANO_ACCESS_KEY=
VOLCANO_SECRET_KEY=

AI_WORKER_CONCURRENCY=4
VIDEO_WORKER_CONCURRENCY=2
AI_RATE_LIMIT_PER_MIN=120

# —— 可选:ES(M2+)——
ES_HOST=
ES_PORT=
ES_USER=
ES_PASSWORD=
ES_INDEX_MATERIALS=materials_video_splits
```

> 实际 `backend/.env` 由用户预配,已包含 MYSQL_* 与 REDIS_* 组件变量;M1 代码从组件拼接 `DATABASE_URL` / `REDIS_URL` / Celery broker / result backend。

```
# backend/.gitignore
__pycache__/
*.pyc
.venv/
.env
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
```

- [ ] **Step 3: 创建 venv 并安装依赖**

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: 无报错,安装 100+ 包。

- [ ] **Step 4: 确认导入可行**

```bash
cd backend && source .venv/bin/activate && python -c "import fastapi, sqlalchemy, alembic, celery, redis, pydantic, ulid; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/.gitignore
git commit -m "feat(backend): 初始化后端工程骨架与依赖清单"
```

---

## Task 2: 配置、日志、ULID、Redis 连通

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/utils/logger.py`
- Create: `backend/app/infra/ulid.py`
- Create: `backend/app/infra/redis_client.py`
- Create: `backend/tests/unit/test_ulid.py`

- [ ] **Step 1: 写 ULID 测试**

```python
# backend/tests/unit/test_ulid.py
import time

from app.infra.ulid import new_id


def test_new_id_is_26_chars_ulid():
    value = new_id()
    assert isinstance(value, str)
    assert len(value) == 26
    assert value.isalnum()


def test_new_id_monotonically_increases():
    # 跨不同毫秒生成的 ULID 必然按时间戳前缀升序;
    # 同毫秒内随机段不保证单调,故用两次取样 + 短 sleep 验证总体单调性
    first = new_id()
    time.sleep(0.002)
    last = new_id()
    assert first < last


def test_new_ids_are_unique():
    ids = {new_id() for _ in range(100)}
    assert len(ids) == 100
```

- [ ] **Step 2: 运行失败**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_ulid.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.infra.ulid'`

- [ ] **Step 3: 实现配置 + ulid + logger + redis**

```python
# backend/app/config.py
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"

    # MySQL(组件式)
    mysql_host: str
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: str = ""
    mysql_database: str
    mysql_database_test: str | None = None

    # Redis(组件式)
    redis_host: str
    redis_port: int = 6379
    redis_db: int = 0
    redis_db_broker: int = 1
    redis_db_result: int = 2

    storage_root: str = "/tmp/comic_drama_assets"
    static_base_url: str = "http://127.0.0.1/static/"

    volcano_access_key: str = ""
    volcano_secret_key: str = ""

    ai_worker_concurrency: int = 4
    video_worker_concurrency: int = 2
    ai_rate_limit_per_min: int = 120

    def _mysql_url(self, db: str) -> str:
        pwd = quote_plus(self.mysql_password)
        return f"mysql+asyncmy://{self.mysql_user}:{pwd}@{self.mysql_host}:{self.mysql_port}/{db}"

    @property
    def database_url(self) -> str:
        return self._mysql_url(self.mysql_database)

    @property
    def database_url_test(self) -> str | None:
        if not self.mysql_database_test:
            return None
        return self._mysql_url(self.mysql_database_test)

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_broker_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_broker}"

    @property
    def celery_result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_result}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# backend/app/utils/logger.py
import logging
import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

```python
# backend/app/infra/ulid.py
from ulid import ULID


def new_id() -> str:
    return str(ULID())
```

```python
# backend/app/infra/redis_client.py
import redis.asyncio as redis_async
from app.config import get_settings

_pool: redis_async.Redis | None = None


def get_redis() -> redis_async.Redis:
    global _pool
    if _pool is None:
        _pool = redis_async.from_url(get_settings().redis_url, decode_responses=True)
    return _pool
```

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_ulid.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/utils/logger.py backend/app/infra/ulid.py backend/app/infra/redis_client.py backend/tests/unit/test_ulid.py
git commit -m "feat(backend): 配置/日志/ULID/redis 客户端基础设施"
```

---

## Task 3: DB 异步引擎与 base model

**Files:**
- Create: `backend/app/infra/db.py`
- Create: `backend/app/domain/models/__init__.py`
- Create: `backend/app/domain/models/base.py`
- Create: `backend/app/deps.py`

- [ ] **Step 1: 实现 DB 引擎**

```python
# backend/app/infra/db.py
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            future=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory
```

- [ ] **Step 2: Base ORM**

```python
# backend/app/domain/models/__init__.py
from .base import Base, TimestampMixin
from .project import Project
from .job import Job

__all__ = ["Base", "TimestampMixin", "Project", "Job"]
```

```python
# backend/app/domain/models/base.py
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 3: 依赖注入**

```python
# backend/app/deps.py
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
```

> 注意:Task 4 创建 `project.py` / `job.py` 前,`__init__.py` 的 import 会先失败,这是预期(下一步就补)。

- [ ] **Step 4: Commit**

```bash
git add backend/app/infra/db.py backend/app/domain/models/base.py backend/app/deps.py
git commit -m "feat(backend): 异步 DB 引擎、session 工厂与 DeclarativeBase"
```

---

## Task 4: `projects` 与 `jobs` ORM 模型

**Files:**
- Create: `backend/app/domain/models/project.py`
- Create: `backend/app/domain/models/job.py`
- Modify: `backend/app/domain/models/__init__.py`(Task 3 已占位)

- [ ] **Step 1: 实现 Project 模型**

```python
# backend/app/domain/models/project.py
from sqlalchemy import CHAR, Enum, JSON, SmallInteger, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id
from app.pipeline.states import ProjectStageRaw

STAGE_VALUES = [s.value for s in ProjectStageRaw]


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[str] = mapped_column(
        Enum(*STAGE_VALUES, name="project_stage"), nullable=False, default=ProjectStageRaw.DRAFT.value
    )
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ratio: Mapped[str] = mapped_column(String(16), default="9:16", nullable=False)
    story: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_stats: Mapped[list | None] = mapped_column(JSON, nullable=True)
    setup_params: Mapped[list | None] = mapped_column(JSON, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_shots: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
```

- [ ] **Step 2: 实现 Job 模型(仅建表,M1 不写业务)**

```python
# backend/app/domain/models/job.py
from sqlalchemy import CHAR, Enum, JSON, SmallInteger, String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id

JOB_KIND_VALUES = [
    "parse_novel", "gen_storyboard", "gen_character_asset", "gen_scene_asset",
    "render_shot", "render_batch", "export_video",
]
JOB_STATUS_VALUES = ["queued", "running", "succeeded", "failed", "canceled"]


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
    kind: Mapped[str] = mapped_column(Enum(*JOB_KIND_VALUES, name="job_kind"), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*JOB_STATUS_VALUES, name="job_status"), nullable=False, default="queued"
    )
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    done: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 3: 冒烟验证模型可实例化**

```bash
cd backend && source .venv/bin/activate && python -c "from app.domain.models import Project, Job; print(Project.__tablename__, Job.__tablename__)"
```

Expected: `projects jobs`(需先完成 Task 5 的 states.py 才能导入成功 — 本任务暂允许 import 失败,Task 5 完成后再回归)

- [ ] **Step 4: Commit**

```bash
git add backend/app/domain/models/project.py backend/app/domain/models/job.py backend/app/domain/models/__init__.py
git commit -m "feat(backend): projects/jobs ORM 模型"
```

---

## Task 5: Pipeline 状态机(enum + 跃迁表)

**Files:**
- Create: `backend/app/pipeline/__init__.py`
- Create: `backend/app/pipeline/states.py`
- Create: `backend/app/pipeline/transitions.py`
- Create: `backend/tests/unit/test_pipeline_transitions.py`

- [ ] **Step 1: 先写测试**

```python
# backend/tests/unit/test_pipeline_transitions.py
import pytest
from app.pipeline.states import ProjectStageRaw, is_forward_allowed, is_rollback_allowed


def test_forward_draft_to_storyboard_ready_ok():
    assert is_forward_allowed(ProjectStageRaw.DRAFT, ProjectStageRaw.STORYBOARD_READY)


def test_forward_skip_stage_denied():
    assert not is_forward_allowed(ProjectStageRaw.DRAFT, ProjectStageRaw.CHARACTERS_LOCKED)


def test_forward_backward_denied():
    assert not is_forward_allowed(ProjectStageRaw.RENDERING, ProjectStageRaw.DRAFT)


def test_rollback_backwards_ok():
    assert is_rollback_allowed(ProjectStageRaw.RENDERING, ProjectStageRaw.STORYBOARD_READY)


def test_rollback_same_stage_denied():
    assert not is_rollback_allowed(ProjectStageRaw.RENDERING, ProjectStageRaw.RENDERING)


def test_rollback_forward_denied():
    assert not is_rollback_allowed(ProjectStageRaw.STORYBOARD_READY, ProjectStageRaw.RENDERING)
```

- [ ] **Step 2: 跑测试失败**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_pipeline_transitions.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 states**

```python
# backend/app/pipeline/__init__.py
from .states import ProjectStageRaw, STAGE_ORDER
from .transitions import advance_stage, rollback_stage, InvalidTransition

__all__ = [
    "ProjectStageRaw", "STAGE_ORDER",
    "advance_stage", "rollback_stage", "InvalidTransition",
]
```

```python
# backend/app/pipeline/states.py
from enum import Enum


class ProjectStageRaw(str, Enum):
    DRAFT = "draft"
    STORYBOARD_READY = "storyboard_ready"
    CHARACTERS_LOCKED = "characters_locked"
    SCENES_LOCKED = "scenes_locked"
    RENDERING = "rendering"
    READY_FOR_EXPORT = "ready_for_export"
    EXPORTED = "exported"


STAGE_ORDER: list[ProjectStageRaw] = [
    ProjectStageRaw.DRAFT,
    ProjectStageRaw.STORYBOARD_READY,
    ProjectStageRaw.CHARACTERS_LOCKED,
    ProjectStageRaw.SCENES_LOCKED,
    ProjectStageRaw.RENDERING,
    ProjectStageRaw.READY_FOR_EXPORT,
    ProjectStageRaw.EXPORTED,
]

STAGE_ZH: dict[ProjectStageRaw, str] = {
    ProjectStageRaw.DRAFT: "草稿中",
    ProjectStageRaw.STORYBOARD_READY: "分镜已生成",
    ProjectStageRaw.CHARACTERS_LOCKED: "角色已锁定",
    ProjectStageRaw.SCENES_LOCKED: "场景已匹配",
    ProjectStageRaw.RENDERING: "镜头生成中",
    ProjectStageRaw.READY_FOR_EXPORT: "待导出",
    ProjectStageRaw.EXPORTED: "已导出",
}


def _index(stage: ProjectStageRaw) -> int:
    return STAGE_ORDER.index(stage)


def is_forward_allowed(current: ProjectStageRaw, target: ProjectStageRaw) -> bool:
    return _index(target) == _index(current) + 1


def is_rollback_allowed(current: ProjectStageRaw, target: ProjectStageRaw) -> bool:
    return _index(target) < _index(current)
```

- [ ] **Step 4: 实现 transitions**

```python
# backend/app/pipeline/transitions.py
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import Project
from app.pipeline.states import (
    ProjectStageRaw, is_forward_allowed, is_rollback_allowed,
)


class InvalidTransition(Exception):
    def __init__(self, current: str, target: str, reason: str):
        self.current = current
        self.target = target
        self.reason = reason
        super().__init__(f"非法 stage 跃迁: {current} → {target} ({reason})")


@dataclass
class InvalidatedCounts:
    shots_reset: int = 0
    characters_unlocked: int = 0
    scenes_unlocked: int = 0


async def advance_stage(
    session: AsyncSession, project: Project, target: ProjectStageRaw
) -> None:
    current = ProjectStageRaw(project.stage)
    if not is_forward_allowed(current, target):
        raise InvalidTransition(current.value, target.value, "仅允许按顺序推进一阶")
    project.stage = target.value


async def rollback_stage(
    session: AsyncSession, project: Project, target: ProjectStageRaw
) -> InvalidatedCounts:
    current = ProjectStageRaw(project.stage)
    if not is_rollback_allowed(current, target):
        raise InvalidTransition(current.value, target.value, "只能回退到更早阶段")
    # M1: 下游表(storyboards/characters/scenes)尚未建,只改 stage
    # M2 起此处要按 spec §5.1 清理 scene_id / status / locked
    project.stage = target.value
    return InvalidatedCounts()
```

- [ ] **Step 5: 测试通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_pipeline_transitions.py -v
```

Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/pipeline/__init__.py backend/app/pipeline/states.py backend/app/pipeline/transitions.py backend/tests/unit/test_pipeline_transitions.py
git commit -m "feat(backend): pipeline 状态机与跃迁/回退合法性校验"
```

---

## Task 6: Alembic 初始化与首版迁移

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_init_projects_jobs.py`

- [ ] **Step 1: 生成 alembic 骨架**

```bash
cd backend && source .venv/bin/activate && alembic init --template async alembic
```

Expected: 生成 `alembic.ini` 和 `alembic/` 目录。

- [ ] **Step 2: 配置 alembic.ini 与 env.py**

修改 `backend/alembic.ini`:
```ini
# 把 sqlalchemy.url 改为空,让 env.py 从 settings 读
sqlalchemy.url =
```

替换 `backend/alembic/env.py`:

```python
# backend/alembic/env.py
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.config import get_settings
from app.domain.models import Base  # noqa

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: 确认 backend/.env 可连通**

M1 约定不起 docker,由用户在 `backend/.env` 中预配 MySQL + Redis 连接。确认:

```bash
test -f backend/.env || cp backend/.env.example backend/.env
# 检查 DATABASE_URL / DATABASE_URL_TEST / REDIS_URL 已按实际环境填好,comic_drama_test 库已建
```

连通性自测:

```bash
cd backend && source .venv/bin/activate && python -c "
from sqlalchemy import create_engine, text
import os, dotenv
dotenv.load_dotenv()
url = os.environ['DATABASE_URL'].replace('+asyncmy','+pymysql')
print(create_engine(url).connect().execute(text('SELECT 1')).scalar())
"
```

> 注:以上自测用 pymysql 同步驱动(需 `pip install pymysql` 或 `asyncmy`+事件循环);生产仍用 asyncmy。若不想装 pymysql,跳过自测,直接在 Step 5 的 `alembic upgrade head` 里验证。

- [ ] **Step 4: 生成迁移**

```bash
cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "init projects and jobs" -r "0001"
```

Expected: 生成 `alembic/versions/0001_*.py`,内含 `op.create_table('projects', ...)` 与 `op.create_table('jobs', ...)`。

打开检查,确认两张表字段齐全。

- [ ] **Step 5: 执行迁移**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

Expected: `INFO [alembic.runtime.migration] Running upgrade -> 0001`

验证:
```bash
mysql -h 127.0.0.1 -uroot -ppassword -D comic_drama -e "SHOW TABLES;"
```

Expected: `projects` / `jobs` / `alembic_version` 三行。

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako backend/alembic/versions/
git commit -m "feat(backend): alembic 初始化与 0001 迁移(projects/jobs)"
```

---

## Task 7: Pydantic schemas

**Files:**
- Create: `backend/app/domain/schemas/__init__.py`
- Create: `backend/app/domain/schemas/project.py`
- Create: `backend/app/domain/schemas/job.py`

- [ ] **Step 1: schemas**

```python
# backend/app/domain/schemas/__init__.py
from .project import (
    ProjectCreate, ProjectUpdate, ProjectSummary, ProjectDetail, ProjectRollbackRequest,
    ProjectRollbackResponse, ProjectListResponse,
)

__all__ = [
    "ProjectCreate", "ProjectUpdate", "ProjectSummary", "ProjectDetail",
    "ProjectRollbackRequest", "ProjectRollbackResponse", "ProjectListResponse",
]
```

```python
# backend/app/domain/schemas/project.py
from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    story: str = Field(..., min_length=1)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str = Field(default="9:16", max_length=16)
    # 与 spec §13 / ProjectDetail.setupParams 一致:字符串数组,后端零转换直存直出
    setup_params: list[str] | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str | None = Field(default=None, max_length=16)
    setup_params: list[str] | None = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    stage: str              # 中文
    stage_raw: str          # 英文 ENUM
    genre: str | None
    ratio: str
    storyboard_count: int = 0
    character_count: int = 0
    scene_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(BaseModel):
    id: str
    name: str
    stage: str
    stage_raw: str
    genre: str | None
    ratio: str
    suggestedShots: str = ""
    story: str
    summary: str = ""
    parsedStats: list[str] = []
    setupParams: list[str] = []
    projectOverview: str = ""
    storyboards: list = []
    characters: list = []
    scenes: list = []
    generationProgress: str = "0 / 0 已完成"
    generationNotes: dict = {"input": "", "suggestion": ""}
    generationQueue: list = []
    exportConfig: list[str] = []
    exportDuration: str = ""
    exportTasks: list = []


class ProjectRollbackRequest(BaseModel):
    to_stage: str


class InvalidatedSummary(BaseModel):
    shots_reset: int = 0
    characters_unlocked: int = 0
    scenes_unlocked: int = 0


class ProjectRollbackResponse(BaseModel):
    from_stage: str
    to_stage: str
    invalidated: InvalidatedSummary


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
    total: int
    page: int
    page_size: int
```

```python
# backend/app/domain/schemas/job.py
from datetime import datetime
from pydantic import BaseModel


class JobDetail(BaseModel):
    id: str
    kind: str
    status: str
    progress: int
    total: int | None
    done: int
    result: dict | None
    error_msg: str | None
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: 冒烟**

```bash
cd backend && source .venv/bin/activate && python -c "from app.domain.schemas import ProjectCreate, ProjectDetail; print(ProjectCreate.model_json_schema()['required'])"
```

Expected: `['name', 'story']`

- [ ] **Step 3: Commit**

```bash
git add backend/app/domain/schemas/
git commit -m "feat(backend): 项目 CRUD 与 rollback 的 Pydantic schemas"
```

---

## Task 8: Project service(CRUD + rollback)

**Files:**
- Create: `backend/app/domain/services/__init__.py`
- Create: `backend/app/domain/services/project_service.py`

- [ ] **Step 1: 实现 service**

```python
# backend/app/domain/services/__init__.py
from .project_service import ProjectService

__all__ = ["ProjectService"]
```

```python
# backend/app/domain/services/project_service.py
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/domain/services/
git commit -m "feat(backend): Project service CRUD 与 rollback 转发"
```

---

## Task 9: API 信封、错误处理、健康检查

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/envelope.py`
- Create: `backend/app/api/errors.py`
- Create: `backend/app/api/health.py`

- [ ] **Step 1: 信封与错误**

```python
# backend/app/api/__init__.py
```

```python
# backend/app/api/envelope.py
from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Any = None


def ok(data: Any = None) -> dict:
    return {"code": 0, "message": "ok", "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}
```

```python
# backend/app/api/errors.py
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.envelope import fail
from app.domain.services.project_service import ProjectNotFound
from app.pipeline.transitions import InvalidTransition


class ApiError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400, data=None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data


def register_handlers(app: FastAPI) -> None:

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return JSONResponse(fail(exc.code, exc.message, exc.data), status_code=exc.http_status)

    @app.exception_handler(ProjectNotFound)
    async def handle_not_found(_: Request, exc: ProjectNotFound):
        return JSONResponse(fail(40401, "资源不存在"), status_code=404)

    @app.exception_handler(InvalidTransition)
    async def handle_invalid_transition(_: Request, exc: InvalidTransition):
        return JSONResponse(
            fail(40301, f"当前 stage 不允许该操作: {exc.current} → {exc.target}"),
            status_code=403,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            fail(40001, "参数校验失败", {"errors": exc.errors()}), status_code=422
        )

    @app.exception_handler(Exception)
    async def handle_unknown(_: Request, exc: Exception):
        return JSONResponse(fail(50001, "内部错误"), status_code=500)
```

- [ ] **Step 2: 健康检查**

```python
# backend/app/api/health.py
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.envelope import ok
from app.deps import get_db
from app.infra.redis_client import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    redis = get_redis()
    await redis.ping()
    return ok({"db": "ok", "redis": "ok"})


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return ok({"ready": True})
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/__init__.py backend/app/api/envelope.py backend/app/api/errors.py backend/app/api/health.py
git commit -m "feat(backend): 响应信封、全局错误 handler、健康检查端点"
```

---

## Task 10: Projects CRUD + rollback 路由

**Files:**
- Create: `backend/app/api/projects.py`

- [ ] **Step 1: 实现路由**

```python
# backend/app/api/projects.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.envelope import ok
from app.api.errors import ApiError
from app.deps import get_db
from app.domain.schemas import (
    ProjectCreate, ProjectDetail, ProjectRollbackRequest, ProjectRollbackResponse,
    ProjectSummary, ProjectUpdate,
)
from app.domain.schemas.project import InvalidatedSummary
from app.domain.services import ProjectService
from app.pipeline import ProjectStageRaw

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_summary(p) -> ProjectSummary:
    return ProjectSummary(
        id=p.id, name=p.name,
        stage=ProjectService.stage_zh(p.stage), stage_raw=p.stage,
        genre=p.genre, ratio=p.ratio,
        storyboard_count=0, character_count=0, scene_count=0,  # M1 无下游表
        created_at=p.created_at, updated_at=p.updated_at,
    )


def _to_detail(p) -> ProjectDetail:
    return ProjectDetail(
        id=p.id, name=p.name,
        stage=ProjectService.stage_zh(p.stage), stage_raw=p.stage,
        genre=p.genre, ratio=f"{p.ratio} 竖屏",
        suggestedShots=f"建议镜头数 {p.suggested_shots}" if p.suggested_shots else "",
        story=p.story, summary=p.summary or "",
        parsedStats=p.parsed_stats or [],
        setupParams=p.setup_params or [],
        projectOverview=p.overview or "",
    )


@router.post("", status_code=200)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.create(payload)
    return ok({"id": project.id, "stage": project.stage, "created_at": project.created_at})


@router.get("")
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectService(db)
    items, total = await svc.list(page, page_size)
    return ok({
        "items": [_to_summary(p).model_dump() for p in items],
        "total": total, "page": page, "page_size": page_size,
    })


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.get(project_id)
    return ok(_to_detail(project).model_dump())


@router.patch("/{project_id}")
async def update_project(
    project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    svc = ProjectService(db)
    project = await svc.update(project_id, payload)
    return ok(_to_detail(project).model_dump())


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    await svc.delete(project_id)
    return ok({"deleted": True})


@router.post("/{project_id}/rollback")
async def rollback_project(
    project_id: str, payload: ProjectRollbackRequest, db: AsyncSession = Depends(get_db)
):
    try:
        target = ProjectStageRaw(payload.to_stage)
    except ValueError:
        raise ApiError(40001, f"非法的 to_stage 值: {payload.to_stage}", http_status=422)

    svc = ProjectService(db)
    project, from_stage, invalidated = await svc.rollback(project_id, target)
    resp = ProjectRollbackResponse(
        from_stage=from_stage,
        to_stage=project.stage,
        invalidated=InvalidatedSummary(
            shots_reset=invalidated.shots_reset,
            characters_unlocked=invalidated.characters_unlocked,
            scenes_unlocked=invalidated.scenes_unlocked,
        ),
    )
    return ok(resp.model_dump())
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/projects.py
git commit -m "feat(backend): projects CRUD 与 rollback REST 端点"
```

---

## Task 11: Celery 骨架

**Files:**
- Create: `backend/app/tasks/__init__.py`
- Create: `backend/app/tasks/celery_app.py`

- [ ] **Step 1: 实现**

```python
# backend/app/tasks/__init__.py
from .celery_app import celery_app

__all__ = ["celery_app"]
```

```python
# backend/app/tasks/celery_app.py
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "comic_drama",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_default_queue="ai",
    task_routes={
        "ai.*": {"queue": "ai"},
        "video.*": {"queue": "video"},
    },
)


@celery_app.task(name="ai.ping")
def ping() -> str:
    return "pong"
```

- [ ] **Step 2: 冒烟**

```bash
cd backend && source .venv/bin/activate && celery -A app.tasks.celery_app inspect ping || true
```

(若未启动 worker 会超时,这是预期;只要 celery app 能 import 就行)

验证 import:
```bash
cd backend && source .venv/bin/activate && python -c "from app.tasks import celery_app; print(celery_app.main)"
```

Expected: `comic_drama`

- [ ] **Step 3: Commit**

```bash
git add backend/app/tasks/
git commit -m "feat(backend): Celery 应用骨架与 ai/video 队列路由"
```

---

## Task 12: FastAPI 装配 main.py

**Files:**
- Create: `backend/app/main.py`

- [ ] **Step 1: 实现**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api import health, projects
from app.api.errors import register_handlers
from app.config import get_settings
from app.utils.logger import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    get_logger("app").info("app_start", env=settings.app_env)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Comic Drama Backend", version="0.1.0", lifespan=lifespan)
    register_handlers(app)
    app.include_router(health.router)
    app.include_router(projects.router, prefix="/api/v1")
    return app


app = create_app()
```

- [ ] **Step 2: 启动并冒烟**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
sleep 3
curl -s http://127.0.0.1:8000/healthz | jq
```

Expected: `{"code":0,"message":"ok","data":{"db":"ok","redis":"ok"}}`

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/projects -H 'Content-Type: application/json' \
  -d '{"name":"测试项目","story":"皇城夜雨..."}' | jq
```

Expected:`{"code":0,"message":"ok","data":{"id":"01H...","stage":"draft","created_at":"..."}}`

```bash
# 把上一步的 id 填回来
curl -s http://127.0.0.1:8000/api/v1/projects | jq '.data.items | length'
```

Expected:`>= 1`

关掉:
```bash
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): FastAPI 入口装配与路由挂载"
```

---

## Task 13: 集成测试 — projects CRUD

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_projects_api.py`

- [ ] **Step 1: conftest**

```python
# backend/tests/conftest.py
import asyncio
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings
from app.domain.models import Base
from app.infra import db as db_module


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
    engine = create_async_engine(settings.database_url_test, future=True, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
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
    from sqlalchemy import text
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
```

- [ ] **Step 2: projects API 测试**

```python
# backend/tests/integration/test_projects_api.py
import pytest


@pytest.mark.asyncio
async def test_create_and_get_project(client):
    resp = await client.post("/api/v1/projects", json={
        "name": "测试项目", "story": "从前有座山", "genre": "古风",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    pid = body["data"]["id"]
    assert len(pid) == 26
    assert body["data"]["stage"] == "draft"

    resp = await client.get(f"/api/v1/projects/{pid}")
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "测试项目"
    assert body["data"]["stage"] == "草稿中"
    assert body["data"]["stage_raw"] == "draft"


@pytest.mark.asyncio
async def test_list_projects(client):
    await client.post("/api/v1/projects", json={"name": "A", "story": "a"})
    await client.post("/api/v1/projects", json={"name": "B", "story": "b"})
    resp = await client.get("/api/v1/projects?page=1&page_size=10")
    body = resp.json()
    # 依赖 client fixture 的 TRUNCATE 隔离,精确断言
    assert body["data"]["total"] == 2
    names = sorted(item["name"] for item in body["data"]["items"])
    assert names == ["A", "B"]
    assert all("stage_raw" in item for item in body["data"]["items"])


@pytest.mark.asyncio
async def test_update_project(client):
    r = await client.post("/api/v1/projects", json={"name": "原名", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}", json={"name": "新名"})
    assert r.json()["data"]["name"] == "新名"


@pytest.mark.asyncio
async def test_delete_project(client):
    r = await client.post("/api/v1/projects", json={"name": "待删", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.delete(f"/api/v1/projects/{pid}")
    assert r.json()["data"]["deleted"] is True
    r = await client.get(f"/api/v1/projects/{pid}")
    assert r.json()["code"] == 40401


@pytest.mark.asyncio
async def test_get_project_404(client):
    r = await client.get("/api/v1/projects/01H0000000000000000000NOPE")
    assert r.status_code == 404
    assert r.json()["code"] == 40401


@pytest.mark.asyncio
async def test_create_project_validation(client):
    r = await client.post("/api/v1/projects", json={"name": ""})  # 缺 story
    assert r.status_code == 422
    assert r.json()["code"] == 40001
```

- [ ] **Step 3: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_projects_api.py -v
```

Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py backend/tests/integration/test_projects_api.py
git commit -m "test(backend): projects CRUD 集成测试"
```

---

## Task 14: 集成测试 — rollback

**Files:**
- Create: `backend/tests/integration/test_rollback_api.py`

- [ ] **Step 1: 测试**

```python
# backend/tests/integration/test_rollback_api.py
import pytest
from sqlalchemy import update
from app.domain.models import Project


async def _force_stage(db_session, project_id: str, stage: str) -> None:
    await db_session.execute(update(Project).where(Project.id == project_id).values(stage=stage))
    await db_session.commit()


@pytest.mark.asyncio
async def test_rollback_backward_ok(client, db_session):
    r = await client.post("/api/v1/projects", json={"name": "回退测试", "story": "x"})
    pid = r.json()["data"]["id"]
    await _force_stage(db_session, pid, "rendering")

    r = await client.post(f"/api/v1/projects/{pid}/rollback", json={"to_stage": "storyboard_ready"})
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["from_stage"] == "rendering"
    assert body["data"]["to_stage"] == "storyboard_ready"
    assert body["data"]["invalidated"] == {
        "shots_reset": 0, "characters_unlocked": 0, "scenes_unlocked": 0,
    }


@pytest.mark.asyncio
async def test_rollback_forward_denied(client):
    r = await client.post("/api/v1/projects", json={"name": "回退前进", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/projects/{pid}/rollback", json={"to_stage": "rendering"})
    assert r.status_code == 403
    assert r.json()["code"] == 40301


@pytest.mark.asyncio
async def test_rollback_invalid_target(client):
    r = await client.post("/api/v1/projects", json={"name": "非法目标", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/projects/{pid}/rollback", json={"to_stage": "not_a_stage"})
    assert r.status_code == 422
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_rollback_same_stage_denied(client, db_session):
    r = await client.post("/api/v1/projects", json={"name": "同阶段", "story": "x"})
    pid = r.json()["data"]["id"]
    await _force_stage(db_session, pid, "storyboard_ready")
    r = await client.post(f"/api/v1/projects/{pid}/rollback", json={"to_stage": "storyboard_ready"})
    assert r.status_code == 403
    assert r.json()["code"] == 40301
```

- [ ] **Step 2: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_rollback_api.py -v
```

Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_rollback_api.py
git commit -m "test(backend): rollback 端点集成测试(合法回退/前进拒绝/非法目标/同阶段拒绝)"
```

---

## Task 15: Dockerfile 与 docker-compose(**可选,M1 DoD 不要求构建通过**)

> **注**:M1 约定不走 docker 本地部署,本任务产物仅为后续里程碑的预留文件。若本次不执行,可跳过整个 Task 15,并在后续需要时单独补一个 PR。若要写入,按下列顺序保证构建正确。

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/docker-compose.yml`

- [ ] **Step 1: Dockerfile**(先 COPY 源码再 editable install)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# 先把构建 editable install 所需的全部文件 COPY 进去,再安装
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: docker-compose**

```yaml
# backend/docker-compose.yml
version: "3.9"

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: password
      MYSQL_DATABASE: comic_drama
    ports: ["3306:3306"]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-ppassword"]
      interval: 5s
      retries: 20

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: .
    env_file: .env
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_started
    ports: ["8000:8000"]
    command: >
      sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

  celery-ai:
    build: .
    env_file: .env
    depends_on: [mysql, redis]
    command: celery -A app.tasks.celery_app worker -Q ai -c 4 --loglevel=INFO

  celery-video:
    build: .
    env_file: .env
    depends_on: [mysql, redis]
    command: celery -A app.tasks.celery_app worker -Q video -c 2 --loglevel=INFO
```

- [ ] **Step 3: 冒烟(可选)**

若本机已装 docker,运行:

```bash
cd backend && docker-compose build api
```

Expected: 无报错,镜像构建成功。

若本机未装 docker,跳过此步 — M1 DoD 不要求 docker 构建。

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile backend/docker-compose.yml
git commit -m "feat(backend): Dockerfile 与 docker-compose(api/celery-ai/celery-video/mysql/redis)"
```

---

## Task 16: M1 冒烟脚本与 README

**Files:**
- Create: `backend/scripts/smoke_m1.sh`
- Create: `backend/README.md`

- [ ] **Step 1: smoke 脚本**

```bash
# backend/scripts/smoke_m1.sh
#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}

echo "[1/5] healthz"
curl -fsS "$BASE/healthz" | jq .

echo "[2/5] create project"
PID=$(curl -fsS -X POST "$BASE/api/v1/projects" \
  -H 'Content-Type: application/json' \
  -d '{"name":"冒烟项目","story":"从前有座山","genre":"古风"}' | jq -r .data.id)
echo "created: $PID"

echo "[3/5] get project"
curl -fsS "$BASE/api/v1/projects/$PID" | jq '.data | {id, stage, stage_raw, name}'

echo "[4/5] rollback to same stage(应拒绝,预期 HTTP 403 + code=40301)"
RB_BODY=$(mktemp)
RB_CODE=$(curl -s -o "$RB_BODY" -w '%{http_code}' \
  -X POST "$BASE/api/v1/projects/$PID/rollback" \
  -H 'Content-Type: application/json' \
  -d '{"to_stage":"draft"}')
jq . "$RB_BODY"
if [[ "$RB_CODE" != "403" ]]; then
  echo "❌ expected HTTP 403, got $RB_CODE"; exit 1
fi
if [[ "$(jq -r .code "$RB_BODY")" != "40301" ]]; then
  echo "❌ expected body.code=40301"; exit 1
fi
rm -f "$RB_BODY"

echo "[5/5] delete"
curl -fsS -X DELETE "$BASE/api/v1/projects/$PID" | jq .

echo "✅ smoke passed"
```

```bash
chmod +x backend/scripts/smoke_m1.sh
```

- [ ] **Step 2: README**

```markdown
# Comic Drama Backend (M1)

## 快速开始

\`\`\`bash
# 1. 启动 MySQL & Redis(本地 docker 或外部实例)
docker-compose up -d mysql redis

# 2. 配置环境
cp .env.example .env   # 编辑 DATABASE_URL 等

# 3. 虚拟环境
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 4. 迁移
alembic upgrade head

# 5. 启动 API
uvicorn app.main:app --reload --port 8000

# 6. 冒烟
./scripts/smoke_m1.sh
\`\`\`

## 测试

\`\`\`bash
pytest -v
\`\`\`

## M1 范围

- 项目 CRUD(POST/GET/PATCH/DELETE /api/v1/projects)
- 阶段回退 POST /api/v1/projects/{id}/rollback
- 健康检查 /healthz /readyz
- Celery 应用装配(仅 ping 任务)
- MySQL projects/jobs 表

## M1 不包含

- 小说解析、分镜生成、角色/场景资产、镜头渲染、视频导出 — 见 M2 起
- 真实 AI 调用 — 见 M3a
- 鉴权 — MVP 范围外
```

- [ ] **Step 3: 运行 smoke**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 &
sleep 3
./scripts/smoke_m1.sh
kill %1
```

Expected: 所有步骤 ✅

- [ ] **Step 4: 跑全量测试**

```bash
cd backend && source .venv/bin/activate && pytest -v
```

Expected: 全部 passed(约 12+ 测试)

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/smoke_m1.sh backend/README.md
git commit -m "docs(backend): M1 冒烟脚本与 README"
```

---

## 完成标准 (Definition of Done)

- [ ] `pytest -v` 全量通过,覆盖 `unit` 与 `integration` 两层;`test_list_projects` 断言 `total == 2`(依赖 fixture TRUNCATE 隔离)
- [ ] `./scripts/smoke_m1.sh` 一次性通过(API 在 127.0.0.1:8000)
- [ ] `alembic upgrade head` 在干净库上可重复执行,`SHOW TABLES` 出 `projects / jobs / alembic_version` 三张
- [ ] 所有端点响应信封均为 `{code, message, data}`,错误码覆盖 40001 / 40301 / 40401 / 50001
- [ ] `GET /api/v1/projects/{id}` 响应同时包含 `stage`(中文)和 `stage_raw`(英文 ENUM)
- [ ] `app.pipeline.transitions` 是唯一写 `project.stage` 的模块(grep 校验)
- [ ] git 提交历史按任务拆分,每个 Task 至少一次 commit
- ~~`docker-compose build api` 构建通过~~ — M1 不使用 docker,Task 15 为可选项,本条不纳入 DoD

---

## 自检(本 plan 写完后的 review)

- **Spec 覆盖**:M1 声明"基础骨架 + 项目 CRUD + rollback 端点 + stage 状态机骨架(mock 阶段跃迁)"。本 plan Task 3-12 覆盖前三项;mock 阶段跃迁留给 M2(本 plan 只建表和建状态机,不写 advance_stage 业务触发) — 符合预期
- **Placeholder 扫描**:本文件内无 TBD / TODO / "implement later" 类占位
- **类型一致性**:`ProjectStageRaw` 在 `states.py` 定义,`project.py` 模型、`transitions.py`、`projects.py` 路由一致引用;`stage_zh` 键值映射与后端 spec §13.2 完全一致
- **与前端契约**:`ProjectDetail` 字段(`stage` / `stage_raw` / `suggestedShots` / `parsedStats` / `setupParams` / `projectOverview` 等驼峰)对齐前端 `ProjectData`;`storyboards`/`characters`/`scenes` 等下游数组在 M1 默认空,前端渲染空态即可

---

## 衔接下一份 plan

- **Backend M2**(分镜生成 + mock VolcanoClient):将补 `storyboards` / `characters` / `scenes` / `shot_renders` / `export_tasks` / `shot_character_refs` / `export_shot_snapshots` 表、实现 `parse_novel` + `gen_storyboard` Celery 任务(mock 返回)、打通 `/parse` 端点与 jobs 轮询
- **Frontend M1**(脚手架迁移):可在本 plan 交付后并行开始,直接联调 `projects` CRUD 与 `/rollback` 两类端点
