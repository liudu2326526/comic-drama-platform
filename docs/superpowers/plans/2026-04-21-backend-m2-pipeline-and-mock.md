# Backend M2: Pipeline + Mock VolcanoClient + 小说解析/分镜生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M1 骨架之上补齐"小说解析 + 分镜生成(假数据)"全链路:新增 storyboards / characters / scenes / shot_character_refs / shot_renders / export_tasks / export_shot_snapshots 共 7 张业务表;实现 mock VolcanoClient(按 `docs/integrations/volcengine-ark-api.md` 定义接口签名,真实调用留 M3a);落 `parse_novel` + `gen_storyboard` 两个 Celery 任务并通过 `pipeline.transitions` 推进 stage;`GET /projects/{id}` 聚合详情真实拼装 storyboards 与生成队列;顺带修完 M1 code review 遗留的 6 个问题(PATCH null 绕过 / setup_params 契约 / 删除 project 级联 jobs / 集成测试走 Alembic / CORS / mypy)。

**Architecture:** 延续 M1 分层(`api` / `domain` / `pipeline` / `tasks` / `infra`)。新增 `app/infra/volcano_client.py` 作为 **唯一** AI 出口(chat + image,mock 实现保留真实接入点);Celery 任务只能调这个 client。状态机不变量:project stage、job progress、非初始状态迁移统一经 `pipeline.transitions.*`;storyboard 内容 CRUD 由 `StoryboardService` 负责,但所有写路径必须先调用 pipeline 的 editable guard。测试用 `CELERY_TASK_ALWAYS_EAGER=True`,使异步任务在 FastAPI 请求上下文内同步执行,避免拉 worker。

**Tech Stack:** 延续 M1(Python 3.11 / FastAPI / SQLAlchemy 2.x async / Alembic / Celery 5 / Redis / MySQL 8 / pytest-asyncio)。新增 `openai==1.30.1`(M3a 才会真正调用,M2 仅预装并在 mock client 里 import guard)、`fastapi[all]` 自带 CORS,无需额外依赖。

**References:**
- 设计文档:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md`
- 火山 API 契约:`docs/integrations/volcengine-ark-api.md`
- M1 plan:`docs/superpowers/plans/2026-04-20-backend-m1-skeleton.md`
- 前端契约:`docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §9 + `ProjectData` 类型

---

## M1 Review 处理决策(用户提出的 6 条)

| 严重度 | 问题 | 处理落点 |
|---|---|---|
| High | PATCH 允许 `{"name": null}` 把非空字段置空;`name: ""` 绕过创建 `min_length=1` | Task 2:`ProjectUpdate` 加 `model_validator` 禁止显式 null,`name`/`ratio` 加 `min_length=1`;`ProjectCreate.name` 同步加 `min_length=1`(已有但被空串绕过,补校验) |
| Medium | `setup_params` 契约不一致(spec §6.3.1 是对象 / 代码是 list[str] / spec §13 是 string[]) | **统一为 `list[str]`**。Task 15 改 spec §6.3.1 示例;代码保持不变,补拒绝 dict 的测试 |
| Medium | 删除 project 不级联清理 jobs(M1 允许,M2 写 jobs 后会留孤儿) | Task 6:Alembic 0002 给 `jobs.project_id` 加 FK + `ON DELETE CASCADE`;ORM 同步加 `ForeignKey`;Task 14 写集成测试 |
| Medium | 集成测试走 `Base.metadata.create_all`,绕过 Alembic,migration 漂移不会被发现 | Task 3:`conftest.test_engine` 改为先 drop 测试库所有表再 `alembic upgrade head`;另加一个"迁移幂等"显式用例 |
| Low | 前端联调跨域/代理 | Task 13:后端加 CORS 白名单(dev:`http://localhost:5173` / `http://127.0.0.1:5173`);Vite proxy 留给前端 M1 计划,本 plan 不写前端 |
| Low | mypy 跑不过(Settings 必填参数、celery stub) | Task 1:`pyproject.toml` 加 `[tool.mypy]` + `plugins = ["pydantic.mypy"]` + `celery.*` `ignore_missing_imports`;DoD 要求 `mypy app` 通过 |

---

## M2 范围边界(按 spec §15)

**包含**:
- 7 张业务表 ORM + Alembic 迁移
- mock VolcanoClient(chat / image)
- `parse_novel` + `gen_storyboard` 两个 Celery 任务(mock 数据)
- `/projects/{id}/parse` 触发 + `/jobs/{id}` 轮询 + `/projects/{id}/storyboards` CRUD / reorder / confirm
- `GET /projects/{id}` 聚合详情拼真实 storyboards + generationQueue + generationProgress
- pipeline 扩展:storyboard 状态 + rollback 级联清理 + 编辑窗口 guard
- CORS + mypy + 测试走 Alembic
- 修 M1 review 6 条

**不包含(留给后续 milestone)**:
- 真实火山 API 调用(M3a)
- 角色/场景资产的**数据生成**(表已建,数据留 M3a;M2 聚合详情里 `characters`/`scenes` 数组为 `[]`)
- 镜头渲染(M3b/c)
- 导出(M4)
- 断点续跑扫描(M5)
- 角色主角唯一性 DB 兜底约束(MVP 不做)

---

## 文件结构(M2 交付)

**新建**:

```
backend/
├── alembic/versions/
│   └── 0002_business_tables_and_jobs_fk.py
├── app/
│   ├── api/
│   │   ├── jobs.py
│   │   └── storyboards.py
│   ├── domain/
│   │   ├── models/
│   │   │   ├── storyboard.py
│   │   │   ├── character.py
│   │   │   ├── scene.py
│   │   │   ├── shot_render.py
│   │   │   └── export_task.py
│   │   ├── schemas/
│   │   │   ├── storyboard.py
│   │   │   └── job.py           # M1 占位过,本期补齐
│   │   └── services/
│   │       ├── storyboard_service.py
│   │       ├── job_service.py
│   │       └── aggregate_service.py
│   ├── infra/
│   │   └── volcano_client.py
│   ├── pipeline/
│   │   └── storyboard_states.py
│   └── tasks/
│       └── ai/
│           ├── __init__.py
│           ├── parse_novel.py
│           └── gen_storyboard.py
└── tests/
    ├── unit/
    │   ├── test_schema_validation.py
    │   ├── test_volcano_mock.py
    │   ├── test_rollback_cascade.py
    │   └── test_storyboard_states.py
    └── integration/
        ├── test_alembic_migration.py
        ├── test_parse_flow.py
        ├── test_storyboards_api.py
        ├── test_jobs_api.py
        ├── test_project_delete_cascade.py
        └── test_cors.py
```

**修改**:

```
backend/
├── pyproject.toml                           # Task 1
├── app/
│   ├── config.py                            # Task 8:ALWAYS_EAGER / storage_root 注入
│   ├── main.py                              # Task 13:CORS
│   ├── api/projects.py                      # Task 11/12:新增 /parse,聚合详情改造
│   ├── domain/
│   │   ├── models/__init__.py               # Task 4:导出新模型
│   │   ├── models/project.py                # Task 4:relationship 补(可选)
│   │   ├── models/job.py                    # Task 6:ForeignKey
│   │   ├── schemas/__init__.py              # Task 10:导出新 schemas
│   │   ├── schemas/project.py               # Task 2:validator
│   │   └── services/project_service.py      # Task 2:PATCH 不再盲 setattr
│   ├── pipeline/
│   │   ├── states.py                        # Task 5:新增 editable guard
│   │   └── transitions.py                   # Task 5:rollback 级联、update_job_progress
│   └── tasks/celery_app.py                  # Task 8:include ai 包、ALWAYS_EAGER toggle
├── tests/conftest.py                        # Task 3:走 Alembic
└── scripts/smoke_m2.sh                      # Task 16
```

**责任**:
- `app/infra/volcano_client.py`:单一 AI 出口;`VolcanoClient` 接口 + `MockVolcanoClient` 实现 + `get_volcano_client()` 工厂(按 `AI_PROVIDER_MODE=mock|real` 路由,M2 只走 mock)
- `app/pipeline/storyboard_states.py`:StoryboardStatus ENUM + 合法跃迁
- `app/pipeline/transitions.py`:扩展 `rollback_stage` 真级联、`confirm_storyboards`(draft|storyboard_ready → storyboard_ready 的幂等化)、`update_job_progress`、`finalize_job`
- `app/tasks/ai/parse_novel.py`:读 project.story → chat mock → 写 summary/parsed_stats/overview/suggested_shots → chain `gen_storyboard`
- `app/tasks/ai/gen_storyboard.py`:chat mock 返回 8~12 条分镜 → 批量 insert storyboards → `transitions.advance_stage(draft → storyboard_ready)`
- `app/domain/services/aggregate_service.py`:一处拼 `ProjectDetail`(storyboards / characters / scenes / generationQueue / generationProgress / exportConfig / exportDuration / exportTasks)
- `app/domain/services/job_service.py`:jobs CRUD,配合 transitions 更新进度

---

## 实施前提

- M1 已合入 `feat/backend-m1`,`pytest -v` 全绿,`alembic upgrade head` 在业务库与 `creative_platform_test` 上都可执行
- MySQL `creative_platform_test` 测试库可见,且之前 M1 conftest 用 `create_all` 建的表需要先手动 drop(Task 3 会改 fixture 自动处理)
- `backend/.env` 已有 M1 所有变量;本 plan 额外要求 `AI_PROVIDER_MODE=mock`、`BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`
- 工作目录默认 repo 根;命令示例除非显式 `cd backend`,否则都已 `cd backend`

---

## Task 1: 升级 pyproject — mypy 配置 + openai 依赖 + CORS 语义梳理

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 在 dependencies 追加 openai(M2 import guard,M3a 真实使用)**

把 `backend/pyproject.toml` 的 `dependencies` 段追加一行:

```toml
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
  "openai==1.30.1",
]
```

FastAPI 自带的 `fastapi.middleware.cors.CORSMiddleware` 不需要任何新依赖。

- [ ] **Step 2: 追加 mypy 配置**

在 `pyproject.toml` 文末追加:

```toml
[tool.mypy]
python_version = "3.11"
plugins = ["pydantic.mypy"]
explicit_package_bases = true
mypy_path = "."
files = ["app"]
ignore_missing_imports = false
warn_unused_ignores = true
disallow_untyped_defs = false
check_untyped_defs = true

[[tool.mypy.overrides]]
module = ["celery.*", "celery", "kombu.*", "asyncmy.*", "ulid", "ulid.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
# pydantic-settings 从环境变量读 required 字段,mypy 看不到,放开 call-arg
module = ["app.config"]
disable_error_code = ["call-arg"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_untyped_fields = true
```

- [ ] **Step 3: 重新安装依赖**

```bash
cd backend && source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: 安装 `openai` 成功,无报错。

- [ ] **Step 4: 运行 mypy 确认通过**

```bash
cd backend && source .venv/bin/activate && mypy app
```

Expected: `Success: no issues found in NN source files`。若仍有残留报错(例如 M1 遗留的 None-check),按报错直接修 app/ 下对应文件的类型注解 — 允许 inline 小改,不改逻辑。

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore(backend): 补 mypy 配置与 openai 依赖,修复 M1 mypy 跑不过的遗留"
```

---

## Task 2: Pydantic schema 严格化 — 禁止 PATCH 显式 null + 空串

**Files:**
- Modify: `backend/app/domain/schemas/project.py`
- Modify: `backend/app/domain/services/project_service.py`
- Create: `backend/tests/unit/test_schema_validation.py`

- [ ] **Step 1: 先写失败的单元测试**

```python
# backend/tests/unit/test_schema_validation.py
import pytest
from pydantic import ValidationError

from app.domain.schemas.project import ProjectCreate, ProjectUpdate


class TestProjectCreate:
    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ProjectCreate(name="", story="x")
        assert any(e["loc"] == ("name",) for e in exc.value.errors())

    def test_whitespace_name_rejected(self):
        # 纯空白也应当被拒(strip 后为空)
        with pytest.raises(ValidationError):
            ProjectCreate(name="   ", story="x")

    def test_empty_story_rejected(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="n", story="")

    def test_setup_params_must_be_list(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="n", story="x", setup_params={"era": "古风"})  # type: ignore[arg-type]

    def test_valid(self):
        p = ProjectCreate(name="测试", story="  故事  ", setup_params=["古风", "冷色调"])
        assert p.name == "测试"
        # story 不 trim,保留用户原文本
        assert p.story == "  故事  "


class TestProjectUpdate:
    def test_empty_payload_ok(self):
        # {} 合法,什么都不改
        p = ProjectUpdate()
        assert p.model_dump(exclude_unset=True) == {}

    def test_explicit_null_name_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ProjectUpdate(name=None)
        assert any("null" in e["msg"].lower() or "none" in e["msg"].lower()
                   for e in exc.value.errors())

    def test_explicit_null_ratio_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(ratio=None)

    def test_explicit_null_setup_params_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(setup_params=None)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(name="")

    def test_partial_ok(self):
        p = ProjectUpdate(name="新名")
        assert p.model_dump(exclude_unset=True) == {"name": "新名"}

    def test_setup_params_list_ok(self):
        p = ProjectUpdate(setup_params=["A", "B"])
        assert p.model_dump(exclude_unset=True) == {"setup_params": ["A", "B"]}

    def test_setup_params_dict_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(setup_params={"era": "古风"})  # type: ignore[arg-type]
```

- [ ] **Step 2: 跑测试失败**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_schema_validation.py -v
```

Expected: `test_whitespace_name_rejected` / `test_explicit_null_*` / `test_empty_name_rejected`(Update 侧)全部 FAIL。

- [ ] **Step 3: 改 schema 加校验**

```python
# backend/app/domain/schemas/project.py
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    story: str = Field(..., min_length=1)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str = Field(default="9:16", min_length=1, max_length=16)
    # 与 spec §13 和 ProjectDetail.setupParams 一致:字符串数组,后端零转换直存直出
    setup_params: list[str] | None = None

    @model_validator(mode="after")
    def _reject_blank(self) -> "ProjectCreate":
        if not self.name.strip():
            raise ValueError("name 不能为空白")
        return self


class ProjectUpdate(BaseModel):
    """
    PATCH 语义:字段「可省略但不可显式 null」。

    - 省略字段  → model_dump(exclude_unset=True) 里没有这个 key,service 层不 setattr
    - 传字符串 → 按新值写入
    - 传 null   → 422(Pydantic validator 拒绝)
    """
    name: str | None = Field(default=None, min_length=1, max_length=128)
    genre: str | None = Field(default=None, max_length=64)
    ratio: str | None = Field(default=None, min_length=1, max_length=16)
    setup_params: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for field in ("name", "genre", "ratio", "setup_params"):
            if field in data and data[field] is None:
                raise ValueError(f"{field} 不允许显式为 null;若不想修改请省略该字段")
        return data


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

- [ ] **Step 4: service 层 PATCH 去除盲 setattr**

```python
# backend/app/domain/services/project_service.py (update 方法替换)
    async def update(self, project_id: str, payload: ProjectUpdate) -> Project:
        project = await self.get(project_id)
        # model_dump(exclude_unset=True) 只包含用户显式提交的字段;Task 2 的 validator
        # 已经拒绝了显式 null,所以这里的 value 一定是合法非 None 值(除了 setup_params
        # 本身字段类型允许 None,但 validator 已经阻断)。
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(project, field, value)
        return project
```

> 注:其他方法保持不动,只改 `update` 方法体的注释。

- [ ] **Step 5: 跑单元测试通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_schema_validation.py -v
```

Expected: 11 passed

- [ ] **Step 6: 回归 M1 集成测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/ -v
```

Expected: M1 的 10 个集成测试依然全绿。

- [ ] **Step 7: 补集成测试覆盖 PATCH null / 空串**

在 `backend/tests/integration/test_projects_api.py` **末尾追加**(不要覆盖已有测试):

```python
@pytest.mark.asyncio
async def test_patch_explicit_null_rejected(client):
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s"})
    pid = r.json()["data"]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}", json={"name": None})
    assert r.status_code == 422
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_patch_empty_payload_noop(client):
    r = await client.post("/api/v1/projects", json={"name": "原名", "story": "s"})
    pid = r.json()["data"]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}", json={})
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "原名"


@pytest.mark.asyncio
async def test_create_blank_name_rejected(client):
    r = await client.post("/api/v1/projects", json={"name": "   ", "story": "s"})
    assert r.status_code == 422
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_create_setup_params_dict_rejected(client):
    r = await client.post("/api/v1/projects", json={
        "name": "n", "story": "s", "setup_params": {"era": "古风"},
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40001
```

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_projects_api.py -v
```

Expected: 原 6 测 + 4 新测 = 10 passed。

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/schemas/project.py backend/app/domain/services/project_service.py backend/tests/unit/test_schema_validation.py backend/tests/integration/test_projects_api.py
git commit -m "fix(backend)!: PATCH 拒绝显式 null、create/update 均拒空白 name(M1 review High)"
```

---

## Task 3: 集成测试改走真实 Alembic 迁移

**Files:**
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_alembic_migration.py`

- [ ] **Step 1: 先写一个显式「迁移可落地」的测试**

```python
# backend/tests/integration/test_alembic_migration.py
"""
验证 alembic upgrade head 在干净测试库上可执行,且所有 ORM 表都在。
若迁移脚本与 ORM 漂移(缺表/缺列/类型不一致),本测试会炸。
"""
import pytest
from sqlalchemy import inspect

from app.domain.models import Base


@pytest.mark.asyncio
async def test_alembic_creates_all_orm_tables(test_engine):
    async with test_engine.connect() as conn:

        def _list_tables(sync_conn):
            insp = inspect(sync_conn)
            return set(insp.get_table_names())

        actual = await conn.run_sync(_list_tables)

    expected = set(Base.metadata.tables.keys()) | {"alembic_version"}
    missing = expected - actual
    assert not missing, f"alembic 迁移后缺少表: {missing}(actual: {actual})"


@pytest.mark.asyncio
async def test_alembic_columns_match_orm(test_engine):
    """每张表的列名集合必须与 ORM 一致。类型差异不校验(MySQL 方言差异太多)。"""
    async with test_engine.connect() as conn:

        def _collect(sync_conn):
            insp = inspect(sync_conn)
            out: dict[str, set[str]] = {}
            for t in Base.metadata.tables.keys():
                out[t] = {c["name"] for c in insp.get_columns(t)}
            return out

        actual = await conn.run_sync(_collect)

    for table_name, orm_table in Base.metadata.tables.items():
        orm_cols = {c.name for c in orm_table.columns}
        assert actual[table_name] == orm_cols, (
            f"表 {table_name} 列集合漂移: orm={orm_cols} vs db={actual[table_name]}"
        )
```

- [ ] **Step 2: 改 conftest 走 Alembic**

替换 `backend/tests/conftest.py` 的 `test_engine` fixture(其他 fixture 不动)。完整文件:

```python
# backend/tests/conftest.py
import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
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


def _run_alembic_upgrade_head(test_async_url: str) -> None:
    """
    以 tests/ 为 CWD 找不到 alembic.ini,显式指向 backend/alembic.ini。
    直接传 async URL:env.py 里用 `async_engine_from_config` 吃这份 URL,
    无需再引入同步驱动(pymysql 没声明为依赖)。
    """
    backend_root = Path(__file__).resolve().parents[1]
    cfg = AlembicConfig(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", test_async_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncEngine:
    settings = get_settings()
    assert settings.database_url_test, (
        "MYSQL_DATABASE_TEST 未设置,拒绝在业务库上跑集成测试。"
        "请在 backend/.env 中添加 MYSQL_DATABASE_TEST=<test库名> 并提前建库。"
    )
    assert settings.database_url_test != settings.database_url, (
        "MYSQL_DATABASE_TEST 与 MYSQL_DATABASE 相同,会污染业务数据,拒绝运行。"
    )

    # 先用异步 engine drop 所有历史表(含 alembic_version),清零后再跑迁移
    engine = create_async_engine(
        settings.database_url_test, future=True, poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        # drop Base.metadata 已知表
        await conn.run_sync(Base.metadata.drop_all)
        # 再补 drop alembic_version(Base 里没定义)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    await engine.dispose()

    # 再跑真实 alembic upgrade head。env.py 的 run_migrations_online() 内部会
    # asyncio.run(...);当前 fixture 已在事件循环里,所以丢到线程中执行,
    # 避免 "asyncio.run() cannot be called from a running event loop"。
    await asyncio.to_thread(_run_alembic_upgrade_head, settings.database_url_test)

    # 重建 async engine 供 fixture 下游用
    engine = create_async_engine(
        settings.database_url_test, future=True, poolclass=NullPool
    )
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
    db_module._engine = test_engine
    db_module._session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    async with test_engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE `{t.name}`"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    db_module._engine = None
    db_module._session_factory = None
```

- [ ] **Step 3: env.py 要支持 override**

查看 `backend/alembic/env.py`,目前 M1 写的是:

```python
config.set_main_option("sqlalchemy.url", get_settings().database_url)
```

这会把 Task 3 传入的 test URL 覆盖掉。修改为"只在 URL 未设置时从 settings 取":

```python
# backend/alembic/env.py  (定位到 set_main_option 那行)
# 仅在调用方未显式传入 sqlalchemy.url 时,从 settings 兜底
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
```

- [ ] **Step 4: 跑迁移测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_alembic_migration.py -v
```

Expected: 2 passed(目前 ORM 只有 projects/jobs,Task 4 建完 7 张表后再次跑应仍绿)。

- [ ] **Step 5: 回归所有集成测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration -v
```

Expected: M1 原 10 个 + Task 2 新 4 个 + Task 3 新 2 个 = 16 passed。

- [ ] **Step 6: Commit**

```bash
git add backend/tests/conftest.py backend/tests/integration/test_alembic_migration.py backend/alembic/env.py
git commit -m "test(backend)!: 集成测试改走真实 alembic upgrade head,新增迁移⇄ORM 漂移检测(M1 review Medium)"
```

---

## Task 4: 新增 7 张业务表的 ORM 模型

**Files:**
- Create: `backend/app/domain/models/storyboard.py`
- Create: `backend/app/domain/models/character.py`
- Create: `backend/app/domain/models/scene.py`
- Create: `backend/app/domain/models/shot_render.py`
- Create: `backend/app/domain/models/export_task.py`
- Modify: `backend/app/domain/models/__init__.py`

- [ ] **Step 1: StoryboardShot + 枚举**

```python
# backend/app/domain/models/storyboard.py
from sqlalchemy import CHAR, DECIMAL, Enum, ForeignKey, Index, JSON, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id

STORYBOARD_STATUS_VALUES = ["pending", "generating", "succeeded", "failed", "locked"]


class StoryboardShot(Base, TimestampMixin):
    __tablename__ = "storyboards"
    __table_args__ = (
        UniqueConstraint("project_id", "idx", name="uq_storyboards_project_idx"),
        Index("ix_storyboards_project_id", "project_id"),
        Index("ix_storyboards_scene_id", "scene_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(DECIMAL(4, 1), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*STORYBOARD_STATUS_VALUES, name="storyboard_status"),
        nullable=False,
        default="pending",
    )
    current_render_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
    # scene_id 的 FK 约束在 Alembic 0002 里显式加(需要 scenes 先建好)
    scene_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
```

- [ ] **Step 2: Character**

```python
# backend/app/domain/models/character.py
from sqlalchemy import Boolean, CHAR, Enum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id

CHARACTER_ROLE_VALUES = ["protagonist", "supporting", "atmosphere"]


class Character(Base, TimestampMixin):
    __tablename__ = "characters"
    __table_args__ = (Index("ix_characters_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    role_type: Mapped[str] = mapped_column(
        Enum(*CHARACTER_ROLE_VALUES, name="character_role_type"),
        nullable=False,
        default="supporting",
    )
    is_protagonist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reference_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_style_ref: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 3: Scene**

```python
# backend/app/domain/models/scene.py
from sqlalchemy import Boolean, CHAR, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin
from app.infra.ulid import new_id


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"
    __table_args__ = (Index("ix_scenes_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    theme: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reference_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_style_ref: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: ShotRender + ShotCharacterRef**

```python
# backend/app/domain/models/shot_render.py
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id

SHOT_RENDER_STATUS_VALUES = ["queued", "running", "succeeded", "failed"]


class ShotRender(Base):
    """镜头生成版本历史。M2 仅建表,不写入业务数据(M3b 起使用)。"""

    __tablename__ = "shot_renders"
    __table_args__ = (
        UniqueConstraint("shot_id", "version_no", name="uq_shot_renders_shot_version"),
        Index("ix_shot_renders_shot_id", "shot_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*SHOT_RENDER_STATUS_VALUES, name="shot_render_status"),
        nullable=False,
        default="queued",
    )
    prompt_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ShotCharacterRef(Base):
    """storyboards ⇄ characters 多对多。复合主键 (shot_id, character_id)。"""

    __tablename__ = "shot_character_refs"

    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 5: ExportTask + ExportShotSnapshot**

```python
# backend/app/domain/models/export_task.py
from datetime import datetime

from sqlalchemy import CHAR, DECIMAL, DateTime, Enum, ForeignKey, Index, JSON, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id

EXPORT_TASK_STATUS_VALUES = ["queued", "running", "succeeded", "failed"]


class ExportTask(Base):
    """M2 建表占位,M4 使用。"""

    __tablename__ = "export_tasks"
    __table_args__ = (Index("ix_export_tasks_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        Enum(*EXPORT_TASK_STATUS_VALUES, name="export_task_status"),
        nullable=False,
        default="queued",
    )
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(DECIMAL(6, 1), nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExportShotSnapshot(Base):
    """导出的镜头版本快照,复合主键 (export_task_id, shot_id)。"""

    __tablename__ = "export_shot_snapshots"

    export_task_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("export_tasks.id", ondelete="CASCADE"), primary_key=True
    )
    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), primary_key=True
    )
    render_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("shot_renders.id", ondelete="RESTRICT"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
```

- [ ] **Step 6: 补 __init__ 导出**

```python
# backend/app/domain/models/__init__.py
from .base import Base, TimestampMixin
from .character import Character
from .export_task import ExportShotSnapshot, ExportTask
from .job import Job
from .project import Project
from .scene import Scene
from .shot_render import ShotCharacterRef, ShotRender
from .storyboard import StoryboardShot

__all__ = [
    "Base",
    "TimestampMixin",
    "Character",
    "ExportShotSnapshot",
    "ExportTask",
    "Job",
    "Project",
    "Scene",
    "ShotCharacterRef",
    "ShotRender",
    "StoryboardShot",
]
```

- [ ] **Step 7: 冒烟 import**

```bash
cd backend && source .venv/bin/activate && python -c "
from app.domain.models import (
    Base, Project, Job, StoryboardShot, Character, Scene,
    ShotCharacterRef, ShotRender, ExportTask, ExportShotSnapshot
)
for t in sorted(Base.metadata.tables.keys()):
    print(t)
"
```

Expected(按字母序):
```
characters
export_shot_snapshots
export_tasks
jobs
projects
scenes
shot_character_refs
shot_renders
storyboards
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/models/
git commit -m "feat(backend): 新增 storyboards/characters/scenes/shot_renders/shot_character_refs/export_tasks/export_shot_snapshots ORM"
```

---

## Task 5: Pipeline 扩展 — storyboard 状态、rollback 级联清理、update_job_progress

**Files:**
- Create: `backend/app/pipeline/storyboard_states.py`
- Modify: `backend/app/pipeline/states.py`
- Modify: `backend/app/pipeline/transitions.py`
- Modify: `backend/app/pipeline/__init__.py`
- Create: `backend/tests/unit/test_storyboard_states.py`
- Create: `backend/tests/unit/test_rollback_cascade.py`

- [ ] **Step 1: 写 storyboard 状态单元测试**

```python
# backend/tests/unit/test_storyboard_states.py
import pytest

from app.pipeline.storyboard_states import (
    STORYBOARD_ALLOWED_TRANSITIONS,
    StoryboardStatus,
    is_storyboard_transition_allowed,
)


def test_pending_to_generating_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.PENDING, StoryboardStatus.GENERATING
    )


def test_generating_to_succeeded_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.GENERATING, StoryboardStatus.SUCCEEDED
    )


def test_generating_to_failed_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.GENERATING, StoryboardStatus.FAILED
    )


def test_failed_to_generating_retry_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.FAILED, StoryboardStatus.GENERATING
    )


def test_succeeded_to_locked_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.SUCCEEDED, StoryboardStatus.LOCKED
    )


def test_pending_to_succeeded_denied():
    # 必须经过 generating
    assert not is_storyboard_transition_allowed(
        StoryboardStatus.PENDING, StoryboardStatus.SUCCEEDED
    )


def test_locked_is_terminal():
    # locked 只能被 rollback 强制重置(不走这条函数);常规跃迁下 locked 是终态
    for tgt in StoryboardStatus:
        if tgt is StoryboardStatus.LOCKED:
            continue
        assert not is_storyboard_transition_allowed(StoryboardStatus.LOCKED, tgt)


def test_transitions_table_has_no_placeholder():
    for src, targets in STORYBOARD_ALLOWED_TRANSITIONS.items():
        assert isinstance(src, StoryboardStatus)
        assert all(isinstance(t, StoryboardStatus) for t in targets)
```

- [ ] **Step 2: 跑测试失败**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_storyboard_states.py -v
```

Expected: `ModuleNotFoundError`。

- [ ] **Step 3: 实现 storyboard 状态**

```python
# backend/app/pipeline/storyboard_states.py
from enum import Enum


class StoryboardStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    LOCKED = "locked"


STORYBOARD_ALLOWED_TRANSITIONS: dict[StoryboardStatus, set[StoryboardStatus]] = {
    StoryboardStatus.PENDING: {StoryboardStatus.GENERATING},
    StoryboardStatus.GENERATING: {StoryboardStatus.SUCCEEDED, StoryboardStatus.FAILED},
    StoryboardStatus.SUCCEEDED: {StoryboardStatus.LOCKED, StoryboardStatus.GENERATING},
    StoryboardStatus.FAILED: {StoryboardStatus.GENERATING},
    StoryboardStatus.LOCKED: set(),  # 终态;rollback 另有独立路径
}


def is_storyboard_transition_allowed(
    current: StoryboardStatus, target: StoryboardStatus
) -> bool:
    return target in STORYBOARD_ALLOWED_TRANSITIONS.get(current, set())
```

> **不变量口径对齐**(同步落在 `backend-mvp-design.md §3` 细化):
> - **INSERT 时设定初始状态**(`shot.status='pending'`、`shot_render.status='queued'`、`export_task.status='queued'`)允许在 service / task 里直接写 —— 这是"造一行",不是状态迁移。
> - **UPDATE 既有行的 status**(包括 Task 5 Step 4 `rollback_stage` 里对所有 shot 的 bulk reset,以及单行的 pending→generating→succeeded/failed→locked)必须走 `pipeline.transitions` 里的函数。
> - 本 plan 遵循上述口径:`StoryboardService.create` 和 `gen_storyboard._run` 的 INSERT 合规;`rollback_stage` 的 bulk reset 位于 `pipeline.transitions` 合规;其他任何 service / API 一律只读,不得直接改 `status`。

- [ ] **Step 4: 扩展 transitions:rollback 级联 + editable guard + job 进度**

替换 `backend/app/pipeline/transitions.py` 的 `rollback_stage` 并**追加**两个函数。完整文件:

```python
# backend/app/pipeline/transitions.py
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Character, Job, Project, Scene, StoryboardShot
from app.pipeline.states import (
    STAGE_ORDER,
    ProjectStageRaw,
    is_forward_allowed,
    is_rollback_allowed,
)
from app.pipeline.storyboard_states import StoryboardStatus


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


STORYBOARD_EDITABLE_STAGES: set[ProjectStageRaw] = {
    ProjectStageRaw.DRAFT,
    ProjectStageRaw.STORYBOARD_READY,
}


def assert_storyboard_editable(project: Project) -> None:
    """在 storyboards 写路径(新增/编辑/删除/reorder)调用。违反即 InvalidTransition → 40301。"""
    current = ProjectStageRaw(project.stage)
    if current not in STORYBOARD_EDITABLE_STAGES:
        raise InvalidTransition(
            current.value,
            "storyboard_edit",
            "只有 draft / storyboard_ready 阶段允许编辑分镜;请先 rollback",
        )


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

    counts = InvalidatedCounts()

    # 仅清理真正被"回退越过"的阶段产物(spec §5.1)。
    # 例:rendering → scenes_locked 只重置渲染状态,不动 scene 绑定与锁定。
    current_idx = STAGE_ORDER.index(current)
    target_idx = STAGE_ORDER.index(target)

    def crossed(threshold: ProjectStageRaw) -> bool:
        t = STAGE_ORDER.index(threshold)
        return current_idx >= t and target_idx < t

    # 1) 越过 RENDERING:清镜头渲染状态(shot_renders 历史与图片保留审计)
    if crossed(ProjectStageRaw.RENDERING):
        reset_render_stmt = (
            update(StoryboardShot)
            .where(StoryboardShot.project_id == project.id)
            .values(
                status=StoryboardStatus.PENDING.value,
                current_render_id=None,
            )
        )
        result = await session.execute(reset_render_stmt)
        counts.shots_reset = result.rowcount or 0

    # 2) 越过 SCENES_LOCKED:清 shot.scene_id + 场景解锁
    if crossed(ProjectStageRaw.SCENES_LOCKED):
        clear_scene_stmt = (
            update(StoryboardShot)
            .where(StoryboardShot.project_id == project.id)
            .values(scene_id=None)
        )
        await session.execute(clear_scene_stmt)
        unlock_scene_stmt = (
            update(Scene)
            .where(Scene.project_id == project.id, Scene.locked.is_(True))
            .values(locked=False)
        )
        result = await session.execute(unlock_scene_stmt)
        counts.scenes_unlocked = result.rowcount or 0

    # 3) 越过 CHARACTERS_LOCKED:角色解锁
    if crossed(ProjectStageRaw.CHARACTERS_LOCKED):
        unlock_char_stmt = (
            update(Character)
            .where(Character.project_id == project.id, Character.locked.is_(True))
            .values(locked=False)
        )
        result = await session.execute(unlock_char_stmt)
        counts.characters_unlocked = result.rowcount or 0

    # 4) 最后改 project.stage
    project.stage = target.value
    return counts


async def update_job_progress(
    session: AsyncSession,
    job_id: str,
    *,
    done: int | None = None,
    total: int | None = None,
    progress: int | None = None,
    status: str | None = None,
) -> Job:
    """唯一允许写 jobs.status/progress/done/total 的函数。"""
    job = await session.get(Job, job_id)
    if job is None:
        raise InvalidTransition("unknown_job", job_id, "job 不存在")
    if done is not None:
        job.done = done
    if total is not None:
        job.total = total
    if progress is not None:
        job.progress = max(0, min(100, progress))
    if status is not None:
        # 简单线性校验:queued→running→(succeeded|failed|canceled)
        allowed = {
            "queued": {"running", "canceled"},
            "running": {"succeeded", "failed", "canceled"},
            "succeeded": set(),
            "failed": {"running"},   # 允许重试
            "canceled": set(),
        }
        if status not in allowed.get(job.status, set()) and status != job.status:
            raise InvalidTransition(job.status, status, "非法 job 状态跃迁")
        job.status = status
        if status in {"succeeded", "failed", "canceled"}:
            job.finished_at = datetime.utcnow()
    return job


async def count_project_storyboards(session: AsyncSession, project_id: str) -> int:
    stmt = select(StoryboardShot.id).where(StoryboardShot.project_id == project_id)
    rows = (await session.execute(stmt)).all()
    return len(rows)
```

- [ ] **Step 5: pipeline/__init__.py 导出新符号**

```python
# backend/app/pipeline/__init__.py
from .states import ProjectStageRaw, STAGE_ORDER, STAGE_ZH
from .storyboard_states import (
    StoryboardStatus,
    is_storyboard_transition_allowed,
)
from .transitions import (
    InvalidTransition,
    InvalidatedCounts,
    advance_stage,
    assert_storyboard_editable,
    count_project_storyboards,
    rollback_stage,
    update_job_progress,
)

__all__ = [
    "ProjectStageRaw",
    "STAGE_ORDER",
    "STAGE_ZH",
    "StoryboardStatus",
    "is_storyboard_transition_allowed",
    "InvalidTransition",
    "InvalidatedCounts",
    "advance_stage",
    "assert_storyboard_editable",
    "count_project_storyboards",
    "rollback_stage",
    "update_job_progress",
]
```

- [ ] **Step 6: rollback 级联单元测试(in-memory SQLite 不行,用集成风格 + db_session)**

```python
# backend/tests/unit/test_rollback_cascade.py
"""
这是跑在真实 MySQL 测试库上的"准单测"(需要 DB),因为 rollback_stage
里走的 UPDATE ... WHERE 必须让 DB 告诉我们 rowcount。
放在 unit/ 下是因为它只测 pipeline 这个子模块,不走 HTTP。
"""
import pytest

from app.domain.models import Character, Project, Scene, StoryboardShot
from app.infra.ulid import new_id
from app.pipeline import ProjectStageRaw, rollback_stage
from app.pipeline.storyboard_states import StoryboardStatus


async def _seed(db_session, stage: str = "rendering") -> Project:
    p = Project(id=new_id(), name="回退", story="x", stage=stage, ratio="9:16")
    db_session.add(p)
    await db_session.flush()
    # 3 条 storyboards,1 条 locked status,1 条 character,1 条 scene
    for i in range(3):
        db_session.add(StoryboardShot(
            id=new_id(), project_id=p.id, idx=i, title=f"t{i}",
            status=StoryboardStatus.SUCCEEDED.value,
            scene_id=new_id(),              # 故意塞个假 scene_id
            current_render_id=new_id(),
        ))
    db_session.add(Character(
        id=new_id(), project_id=p.id, name="A", role_type="protagonist",
        is_protagonist=True, locked=True,
    ))
    db_session.add(Scene(
        id=new_id(), project_id=p.id, name="S1", locked=True,
    ))
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_rollback_clears_storyboard_bindings(db_session):
    p = await _seed(db_session)
    counts = await rollback_stage(db_session, p, ProjectStageRaw.STORYBOARD_READY)
    await db_session.flush()

    assert counts.shots_reset == 3
    assert counts.characters_unlocked == 1
    assert counts.scenes_unlocked == 1

    shots = (await db_session.execute(
        __import__("sqlalchemy").select(StoryboardShot).where(StoryboardShot.project_id == p.id)
    )).scalars().all()
    assert all(s.scene_id is None for s in shots)
    assert all(s.current_render_id is None for s in shots)
    assert all(s.status == "pending" for s in shots)

    chars = (await db_session.execute(
        __import__("sqlalchemy").select(Character).where(Character.project_id == p.id)
    )).scalars().all()
    assert all(not c.locked for c in chars)


@pytest.mark.asyncio
async def test_rollback_to_same_stage_denied(db_session):
    from app.pipeline.transitions import InvalidTransition
    p = await _seed(db_session, stage="storyboard_ready")
    with pytest.raises(InvalidTransition):
        await rollback_stage(db_session, p, ProjectStageRaw.STORYBOARD_READY)


@pytest.mark.asyncio
async def test_rollback_forward_denied(db_session):
    from app.pipeline.transitions import InvalidTransition
    p = await _seed(db_session, stage="draft")
    with pytest.raises(InvalidTransition):
        await rollback_stage(db_session, p, ProjectStageRaw.RENDERING)
```

- [ ] **Step 7: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_storyboard_states.py tests/unit/test_rollback_cascade.py -v
```

Expected: 8 + 3 = 11 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/pipeline/ backend/tests/unit/test_storyboard_states.py backend/tests/unit/test_rollback_cascade.py
git commit -m "feat(backend): pipeline 扩展 storyboard 状态、rollback 级联清理、update_job_progress 单写入口"
```

---

## Task 6: Alembic 0002 — 建 7 张表 + jobs.project_id FK ON DELETE CASCADE

**Files:**
- Modify: `backend/app/domain/models/job.py`(同步加 ForeignKey,避免 ORM 与迁移漂移)
- Create: `backend/alembic/versions/0002_business_tables_and_jobs_fk.py`

- [ ] **Step 1: 先改 ORM,把 jobs.project_id 声明成 ForeignKey**

在 `backend/app/domain/models/job.py` 顶部 import 里追加 `ForeignKey`:

```python
from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Index, JSON, SmallInteger, String, Text
```

然后把 `project_id` 列改为:

```python
    project_id: Mapped[str | None] = mapped_column(
        CHAR(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
```

这样 Task 6 Step 2 的 autogenerate 不会反复提示这条 FK diff,M1 review Medium 那条 ORM 承诺也真正落地。

- [ ] **Step 2: 用 autogenerate 生成草稿**

```bash
cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "business tables and jobs fk cascade" --rev-id "0002"
```

- [ ] **Step 3: 打开生成文件,手工校正**

校正要点:
1. autogenerate 可能把 FK 生成顺序搞反(scenes 未建就给 storyboards 加 scene_id FK)。本次迁移**暂不给 `storyboards.scene_id` 加 FK 约束**(spec 没强制,设计上 scene 可以先被删除,shot 孤儿指针靠 rollback 级联清理)。如果 autogenerate 加了,**手工删掉**。
2. autogenerate 不会主动给 `jobs.project_id` 加 FK — 补上。
3. `down_revision` 必须是 `'0001'`。

手写完整版(覆盖 autogenerate 输出):

```python
# backend/alembic/versions/0002_business_tables_and_jobs_fk.py
"""business tables and jobs fk cascade

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- jobs.project_id 补 FK ON DELETE CASCADE(M1 review Medium)----
    # M1 时期 jobs.project_id 没有 FK,业务库可能已经有指向不存在项目的孤儿行;
    # 若直接 create_foreign_key,MySQL 会抛 errno 1452 拒绝约束。先清理再加约束。
    op.execute(
        """
        DELETE FROM jobs
        WHERE project_id IS NOT NULL
          AND project_id NOT IN (SELECT id FROM projects)
        """
    )
    op.create_foreign_key(
        "fk_jobs_project_id",
        "jobs",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ---- storyboards ----
    op.create_table(
        "storyboards",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("project_id", sa.CHAR(length=26), nullable=False),
        sa.Column("idx", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.DECIMAL(4, 1), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "generating", "succeeded", "failed", "locked",
                name="storyboard_status",
            ),
            nullable=False,
        ),
        # current_render_id 语义上指向 shot_renders.id,但 storyboards 与 shot_renders
        # 存在循环引用;M2 先不加 FK,M3b 引入镜头渲染写入后再补约束/校验。
        sa.Column("current_render_id", sa.CHAR(length=26), nullable=True),
        sa.Column("scene_id", sa.CHAR(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "idx", name="uq_storyboards_project_idx"),
    )
    op.create_index("ix_storyboards_project_id", "storyboards", ["project_id"], unique=False)
    op.create_index("ix_storyboards_scene_id", "storyboards", ["scene_id"], unique=False)

    # ---- characters ----
    op.create_table(
        "characters",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("project_id", sa.CHAR(length=26), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "role_type",
            sa.Enum(
                "protagonist", "supporting", "atmosphere",
                name="character_role_type",
            ),
            nullable=False,
        ),
        sa.Column("is_protagonist", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("reference_image_url", sa.String(length=512), nullable=True),
        sa.Column("video_style_ref", sa.JSON(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_characters_project_id", "characters", ["project_id"], unique=False)

    # ---- scenes ----
    op.create_table(
        "scenes",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("project_id", sa.CHAR(length=26), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("theme", sa.String(length=32), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("reference_image_url", sa.String(length=512), nullable=True),
        sa.Column("video_style_ref", sa.JSON(), nullable=True),
        sa.Column("template_id", sa.String(length=64), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scenes_project_id", "scenes", ["project_id"], unique=False)

    # ---- shot_renders ----
    op.create_table(
        "shot_renders",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("shot_id", sa.CHAR(length=26), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "succeeded", "failed", name="shot_render_status"),
            nullable=False,
        ),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("provider_task_id", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["shot_id"], ["storyboards.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("shot_id", "version_no", name="uq_shot_renders_shot_version"),
    )
    op.create_index("ix_shot_renders_shot_id", "shot_renders", ["shot_id"], unique=False)

    # ---- shot_character_refs ----
    op.create_table(
        "shot_character_refs",
        sa.Column("shot_id", sa.CHAR(length=26), nullable=False),
        sa.Column("character_id", sa.CHAR(length=26), nullable=False),
        sa.PrimaryKeyConstraint("shot_id", "character_id"),
        sa.ForeignKeyConstraint(["shot_id"], ["storyboards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
    )

    # ---- export_tasks ----
    op.create_table(
        "export_tasks",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("project_id", sa.CHAR(length=26), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "succeeded", "failed", name="export_task_status"),
            nullable=False,
        ),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("video_url", sa.String(length=512), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column("duration_sec", sa.DECIMAL(6, 1), nullable=True),
        sa.Column("progress", sa.SmallInteger(), nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_export_tasks_project_id", "export_tasks", ["project_id"], unique=False)

    # ---- export_shot_snapshots ----
    op.create_table(
        "export_shot_snapshots",
        sa.Column("export_task_id", sa.CHAR(length=26), nullable=False),
        sa.Column("shot_id", sa.CHAR(length=26), nullable=False),
        sa.Column("render_id", sa.CHAR(length=26), nullable=False),
        sa.Column("order_idx", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("export_task_id", "shot_id"),
        sa.ForeignKeyConstraint(["export_task_id"], ["export_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shot_id"], ["storyboards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["render_id"], ["shot_renders.id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    op.drop_table("export_shot_snapshots")
    op.drop_index("ix_export_tasks_project_id", table_name="export_tasks")
    op.drop_table("export_tasks")
    op.drop_table("shot_character_refs")
    op.drop_index("ix_shot_renders_shot_id", table_name="shot_renders")
    op.drop_table("shot_renders")
    op.drop_index("ix_scenes_project_id", table_name="scenes")
    op.drop_table("scenes")
    op.drop_index("ix_characters_project_id", table_name="characters")
    op.drop_table("characters")
    op.drop_index("ix_storyboards_scene_id", table_name="storyboards")
    op.drop_index("ix_storyboards_project_id", table_name="storyboards")
    op.drop_table("storyboards")
    op.drop_constraint("fk_jobs_project_id", "jobs", type_="foreignkey")
    # 必须 drop 自定义 ENUM(MySQL 不保留类型字典,这里是 no-op;PostgreSQL 才需要)
```

- [ ] **Step 4: 在业务库上 upgrade**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

Expected:
```
INFO [alembic.runtime.migration] Running upgrade 0001 -> 0002, business tables and jobs fk cascade
```

验证:
```bash
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -D "$MYSQL_DATABASE" -e "SHOW TABLES;"
```

Expected:9 张业务表 + `alembic_version` = 10 行。

- [ ] **Step 5: 测试库自动走 0002(Task 3 已改 conftest)**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_alembic_migration.py -v
```

Expected: 2 passed — 10 张表(含 alembic_version)与 ORM 列集合一致。

- [ ] **Step 6: 回归全量**

```bash
cd backend && source .venv/bin/activate && pytest -v
```

Expected: M1 + Task 2/3/5 的所有测试全绿。

- [ ] **Step 7: Commit**

```bash
git add backend/app/domain/models/job.py backend/alembic/versions/0002_business_tables_and_jobs_fk.py
git commit -m "feat(backend): alembic 0002 建 7 张业务表,jobs.project_id 加 FK ON DELETE CASCADE + ORM 同步(M1 review Medium)"
```

---

## Task 7: Mock VolcanoClient

**Files:**
- Create: `backend/app/infra/volcano_client.py`
- Create: `backend/tests/unit/test_volcano_mock.py`

- [ ] **Step 1: 写单元测试(定义契约)**

```python
# backend/tests/unit/test_volcano_mock.py
import json

import pytest

from app.infra.volcano_client import (
    ChatMessage,
    MockVolcanoClient,
    VolcanoClient,
    get_volcano_client,
)


def test_mock_is_default():
    client = get_volcano_client()
    assert isinstance(client, MockVolcanoClient)
    assert isinstance(client, VolcanoClient)


def test_chat_completion_returns_json_object():
    client = MockVolcanoClient(seed=1)
    resp = client.chat_completion(
        messages=[
            ChatMessage(role="system", content="你是漫画剧本分场助手,输出 JSON"),
            ChatMessage(role="user", content="拆成 6 个分镜"),
        ],
        response_format={"type": "json_object"},
        model="doubao-seed-1-6-251015",
    )
    # 返回 content 必须是可解析 JSON(与真实火山 response_format=json_object 行为一致)
    data = json.loads(resp.content)
    assert isinstance(data, dict)
    assert resp.finish_reason == "stop"
    assert resp.usage.total_tokens > 0


def test_chat_completion_text_mode():
    client = MockVolcanoClient(seed=2)
    resp = client.chat_completion(
        messages=[ChatMessage(role="user", content="概括这段故事")],
        model="doubao-seed-1-6-251015",
    )
    assert isinstance(resp.content, str)
    assert len(resp.content) > 0


def test_image_generation_returns_url():
    client = MockVolcanoClient(seed=3)
    resp = client.image_generation(
        prompt="古风冷宫",
        size="1152x864",
        model="doubao-seedream-4-0-250828",
    )
    assert resp.data[0].url.startswith("mock://")
    assert resp.data[0].size == "1152x864"


def test_mock_deterministic_by_seed():
    """同 seed 同 prompt 返回一致,便于 snapshot 测试。"""
    c1 = MockVolcanoClient(seed=42)
    c2 = MockVolcanoClient(seed=42)
    r1 = c1.chat_completion(
        messages=[ChatMessage(role="user", content="A")],
        model="doubao-seed-1-6-251015",
    )
    r2 = c2.chat_completion(
        messages=[ChatMessage(role="user", content="A")],
        model="doubao-seed-1-6-251015",
    )
    assert r1.content == r2.content


def test_mock_storyboard_fixture():
    """mock 对「分镜生成」意图识别:当 response_format 含 json_object 且系统提示含"分场"
    时,返回合法的 storyboards 数组结构。"""
    client = MockVolcanoClient(seed=7)
    resp = client.chat_completion(
        messages=[
            ChatMessage(role="system", content="你是漫画剧本分场助手,输出 JSON"),
            ChatMessage(role="user", content="给下面小说生成 8 个分镜:皇城夜雨..."),
        ],
        response_format={"type": "json_object"},
        model="doubao-seed-1-6-251015",
    )
    data = json.loads(resp.content)
    assert "shots" in data
    assert 6 <= len(data["shots"]) <= 14
    for shot in data["shots"]:
        assert {"idx", "title", "description", "duration_sec", "tags"} <= set(shot.keys())


def test_mock_parse_novel_fixture():
    """mock 对「小说解析」意图:系统提示含"解析小说"返回 {summary, parsed_stats, overview, suggested_shots}"""
    client = MockVolcanoClient(seed=11)
    resp = client.chat_completion(
        messages=[
            ChatMessage(role="system", content="你是小说解析助手,输出 JSON"),
            ChatMessage(role="user", content="解析以下小说:皇城夜雨..."),
        ],
        response_format={"type": "json_object"},
        model="doubao-seed-1-6-251015",
    )
    data = json.loads(resp.content)
    assert {"summary", "parsed_stats", "overview", "suggested_shots"} <= set(data.keys())
    assert isinstance(data["parsed_stats"], list)
    assert isinstance(data["suggested_shots"], int)
```

- [ ] **Step 2: 跑测试失败**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_volcano_mock.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: 实现 volcano_client.py**

```python
# backend/app/infra/volcano_client.py
"""
火山方舟 API 的应用层客户端抽象。

M2 只提供 Mock 实现,真实调用(openai SDK + ark.cn-beijing.volces.com)留 M3a。
契约字段对齐 docs/integrations/volcengine-ark-api.md §3(图片)§4(对话)。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from app.config import get_settings


# ---------- 数据结构(与火山 OpenAI 兼容 API 字段一致)----------

@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatCompletion:
    content: str
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"] = "stop"
    usage: Usage = field(default_factory=Usage)
    model: str = ""


@dataclass
class ImageItem:
    url: str
    size: str
    b64_json: str | None = None


@dataclass
class ImageGeneration:
    data: list[ImageItem]
    model: str = ""
    usage: Usage = field(default_factory=Usage)


# ---------- 协议 ----------

@runtime_checkable
class VolcanoClient(Protocol):
    def chat_completion(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatCompletion: ...

    def image_generation(
        self,
        *,
        prompt: str,
        model: str,
        size: str = "2048x2048",
        watermark: bool = False,
        response_format: Literal["url", "b64_json"] = "url",
    ) -> ImageGeneration: ...


# ---------- Mock 实现 ----------

# 分镜 mock fixture:8 条足够覆盖前端工作台 UI;tags 与 spec §4.2 对齐
_STORYBOARD_FIXTURE = {
    "shots": [
        {
            "idx": 1,
            "title": "01 冷宫夜雨",
            "description": "沈昭宁独立废井旁,月色清冷,夜雨斜飞",
            "detail": "中景偏特写,镜头缓慢推进,冷月青灰打光,朱砂唇色点睛",
            "duration_sec": 3.2,
            "tags": ["角色:沈昭宁", "场景:冷宫废院", "情绪:孤冷"],
        },
        {
            "idx": 2,
            "title": "02 秘信自来",
            "description": "夜风卷起一封无字信笺,落在沈昭宁脚下",
            "detail": "俯拍特写,慢动作,信纸飘落瞬间定格",
            "duration_sec": 2.6,
            "tags": ["角色:沈昭宁", "场景:冷宫废院", "道具:密信"],
        },
        {
            "idx": 3,
            "title": "03 宫墙疾影",
            "description": "远处宫墙上一道黑影掠过,消失于瓦檐之间",
            "detail": "全景,追随镜头,快速平移,雨丝被剪影切开",
            "duration_sec": 2.8,
            "tags": ["场景:宫墙夜色", "氛围:悬疑"],
        },
        {
            "idx": 4,
            "title": "04 烛影摇红",
            "description": "沈昭宁回到偏殿,烛火被风拂得摇摇欲灭",
            "detail": "近景,烛焰逆光,人物轮廓被描边",
            "duration_sec": 2.4,
            "tags": ["角色:沈昭宁", "场景:偏殿内室"],
        },
        {
            "idx": 5,
            "title": "05 字字惊心",
            "description": "展信细读,字迹在烛下显出血色纹路",
            "detail": "极特写镜头聚焦信纸,渐显血字",
            "duration_sec": 3.0,
            "tags": ["角色:沈昭宁", "道具:密信", "情绪:惊惧"],
        },
        {
            "idx": 6,
            "title": "06 覆灯屏息",
            "description": "沈昭宁猛地吹熄烛火,侧耳听宫外动静",
            "detail": "短切镜头,黑场上保留眼部特写",
            "duration_sec": 2.2,
            "tags": ["角色:沈昭宁", "情绪:紧张"],
        },
        {
            "idx": 7,
            "title": "07 窗外身影",
            "description": "一道修长身影贴在纸窗外,剪影分明",
            "detail": "平视近景,剪影构图,雨声骤大",
            "duration_sec": 2.6,
            "tags": ["场景:偏殿内室", "氛围:对峙"],
        },
        {
            "idx": 8,
            "title": "08 执剑待客",
            "description": "沈昭宁反手执短刃,缓步靠向纸窗",
            "detail": "低机位跟拍,刀锋反光在脸上闪过",
            "duration_sec": 3.4,
            "tags": ["角色:沈昭宁", "道具:短刃", "情绪:决断"],
        },
    ]
}

_PARSE_FIXTURE = {
    "summary": "以沈昭宁在冷宫的一次雨夜密信事件为主线,层层推进人物处境与对立关系,情绪由孤冷转向决断。",
    "parsed_stats": ["字数 1180", "已识别角色 4", "主要场景 3", "风险情节 0"],
    "overview": "开篇雨夜铺陈孤绝底色;密信牵出暗中敌对;以「吹灯迎敌」收束节奏,预留下回悬念。",
    "suggested_shots": 8,
}


def _seeded_rand(seed: int, *parts: str) -> int:
    h = hashlib.sha1()
    h.update(str(seed).encode())
    for p in parts:
        h.update(b"|")
        h.update(p.encode())
    return int(h.hexdigest()[:8], 16)


class MockVolcanoClient:
    """
    不发任何网络请求。按消息内容的启发式识别意图,返回预置 fixture。

    - 系统提示含"分场" → 返回 _STORYBOARD_FIXTURE
    - 系统提示含"解析小说" → 返回 _PARSE_FIXTURE
    - 其他 → 返回一段文字占位
    """

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def chat_completion(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatCompletion:
        system_content = " ".join(m.content for m in messages if m.role == "system")
        user_content = " ".join(m.content for m in messages if m.role == "user")
        wants_json = bool(response_format and response_format.get("type") in ("json_object", "json_schema"))

        if wants_json and ("分场" in system_content or "分镜" in user_content):
            content = json.dumps(_STORYBOARD_FIXTURE, ensure_ascii=False)
        elif wants_json and ("解析小说" in system_content or "解析以下小说" in user_content):
            content = json.dumps(_PARSE_FIXTURE, ensure_ascii=False)
        elif wants_json:
            content = json.dumps({"echo": user_content[:200]}, ensure_ascii=False)
        else:
            content = f"[mock chat] seed={self.seed} user={user_content[:80]}"

        prompt_tokens = max(32, len(user_content) // 2)
        completion_tokens = max(16, len(content) // 2)
        return ChatCompletion(
            content=content,
            finish_reason="stop",
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            model=model,
        )

    def image_generation(
        self,
        *,
        prompt: str,
        model: str,
        size: str = "2048x2048",
        watermark: bool = False,
        response_format: Literal["url", "b64_json"] = "url",
    ) -> ImageGeneration:
        rand = _seeded_rand(self.seed, model, prompt, size)
        mock_url = f"mock://volcano-image/{rand:08x}-{size}.png"
        return ImageGeneration(
            data=[ImageItem(url=mock_url, size=size)],
            model=model,
            usage=Usage(completion_tokens=4096, total_tokens=4096),
        )


# ---------- 工厂 ----------

_instance: VolcanoClient | None = None


def get_volcano_client() -> VolcanoClient:
    """
    目前只返回 MockVolcanoClient。M3a 起:
    - 读 settings.ai_provider_mode == "real" → 返回 RealVolcanoClient(openai SDK)
    """
    global _instance
    if _instance is None:
        _ = get_settings()  # 触发配置加载,便于日后从 settings 读 seed/mode
        _instance = MockVolcanoClient(seed=0)
    return _instance


def reset_volcano_client_for_tests() -> None:
    global _instance
    _instance = None
```

- [ ] **Step 4: 跑单测通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_volcano_mock.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/volcano_client.py backend/tests/unit/test_volcano_mock.py
git commit -m "feat(backend): mock VolcanoClient(chat/image),契约对齐 volcengine-ark-api.md"
```

---

## Task 8: Celery eager 配置 + parse_novel/gen_storyboard 任务

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/tasks/celery_app.py`
- Create: `backend/app/tasks/ai/__init__.py`
- Create: `backend/app/tasks/ai/parse_novel.py`
- Create: `backend/app/tasks/ai/gen_storyboard.py`

- [ ] **Step 1: config 加 ALWAYS_EAGER + provider mode + 同步 engine(Celery 任务用)**

在 `backend/app/config.py` 的 `Settings` 类里追加字段(其余不动):

```python
    # M2 新增
    ai_provider_mode: str = "mock"   # mock | real(real 留 M3a)
    celery_task_always_eager: bool = False

    @property
    def database_url_sync(self) -> str:
        """Celery 任务是同步 Python(非 async),用 pymysql 驱动。"""
        return self.database_url.replace("+asyncmy", "+pymysql")
```

因为 pymysql 没有进 dependencies,改用 `mysql+mysqlconnector` 或让 Celery 任务走 async?**MVP 简化:让 Celery 任务依旧走 async — 在任务里起事件循环跑 async session**(见 Step 3)。所以 `database_url_sync` 留接口但 M2 不用。

- [ ] **Step 2: celery_app.py 增补**

```python
# backend/app/tasks/celery_app.py
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "comic_drama",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ai.parse_novel",
        "app.tasks.ai.gen_storyboard",
    ],
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
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)


@celery_app.task(name="ai.ping")
def ping() -> str:
    return "pong"
```

- [ ] **Step 3: 实现 parse_novel 任务**

```python
# backend/app/tasks/ai/__init__.py
```

```python
# backend/app/tasks/ai/parse_novel.py
"""
读 project.story → 调 VolcanoClient.chat_completion → 写 projects.summary/
parsed_stats/overview/suggested_shots → chain gen_storyboard。
"""
import asyncio
import json
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.models import Job, Project
from app.infra.db import get_engine
from app.infra.volcano_client import ChatMessage, get_volcano_client
from app.pipeline import update_job_progress
from app.tasks.celery_app import celery_app


async def _run(job_id: str, project_id: str) -> None:
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Phase 1:标记 running + 快照 story(事务块内不跨网络)
    async with session_factory() as session, session.begin():
        await update_job_progress(
            session, job_id, status="running", progress=5, total=4, done=0
        )
        project = await session.get(Project, project_id)
        if project is None:
            await update_job_progress(session, job_id, status="failed", progress=0)
            job = await session.get(Job, job_id)
            if job is not None:
                job.error_msg = f"project {project_id} 不存在"
            return
        story_clip = (project.story or "")[:2000]

    # Phase 2:AI 调用放在事务外,避免长事务
    client = get_volcano_client()
    resp = client.chat_completion(
        messages=[
            ChatMessage(role="system", content="你是小说解析助手,输出 JSON"),
            ChatMessage(role="user", content=f"解析以下小说:\n{story_clip}"),
        ],
        model="doubao-seed-1-6-251015",
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    data = json.loads(resp.content)

    # Phase 3:回写解析结果
    async with session_factory() as session, session.begin():
        project = await session.get(Project, project_id)
        if project is None:
            return  # 中途被删
        project.summary = data.get("summary", "")
        project.parsed_stats = data.get("parsed_stats", [])
        project.overview = data.get("overview", "")
        project.suggested_shots = int(data.get("suggested_shots", 8))
        await update_job_progress(session, job_id, progress=50, done=2)

    # Phase 4:链式跑分镜生成。直接 await 协程,不走 Celery .apply() —
    # 避免在 asyncio.run 内部再次 asyncio.run 触发 "cannot be called from a running loop"。
    # worker 模式下这属于同 job 内的顺序子步骤;如要拆分独立 job/队列,留到 M3a。
    from app.tasks.ai.gen_storyboard import _run as _gen_run
    await _gen_run(job_id, project_id)


@celery_app.task(name="ai.parse_novel", bind=True, max_retries=3, default_retry_delay=4)
def parse_novel_task(self, job_id: str, project_id: str) -> dict[str, Any]:
    # Celery worker 模式下无 running loop,asyncio.run 安全。
    # eager 模式不再走此入口(见 /parse 端点的 eager 分支)。
    asyncio.run(_run(job_id, project_id))
    return {"job_id": job_id, "project_id": project_id, "step": "parse_novel_done"}
```

- [ ] **Step 4: 实现 gen_storyboard 任务**

```python
# backend/app/tasks/ai/gen_storyboard.py
import asyncio
import json
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.models import Project, StoryboardShot
from app.infra.db import get_engine
from app.infra.ulid import new_id
from app.infra.volcano_client import ChatMessage, get_volcano_client
from app.pipeline import ProjectStageRaw, advance_stage, update_job_progress
from app.pipeline.storyboard_states import StoryboardStatus
from app.tasks.celery_app import celery_app


async def _run(job_id: str, project_id: str) -> None:
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Phase 1:标记 running + 快照 story
    async with session_factory() as session, session.begin():
        await update_job_progress(
            session, job_id, status="running", progress=55, total=10, done=5
        )
        project = await session.get(Project, project_id)
        if project is None:
            await update_job_progress(session, job_id, status="failed")
            return
        story_clip = (project.story or "")[:1500]

    # Phase 2:AI 调用放在事务外
    client = get_volcano_client()
    resp = client.chat_completion(
        messages=[
            ChatMessage(role="system", content="你是漫画剧本分场助手,输出 JSON"),
            ChatMessage(
                role="user",
                content=f"给下面小说生成 8 个分镜,每条含 idx/title/description/detail/duration_sec/tags:\n{story_clip}",
            ),
        ],
        model="doubao-seed-1-6-251015",
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    shots = json.loads(resp.content).get("shots", [])

    # Phase 3:写入 storyboards + 推进 stage
    async with session_factory() as session, session.begin():
        project = await session.get(Project, project_id)
        if project is None:
            return

        # 幂等:清空旧 storyboards(若是重试)
        await session.execute(
            delete(StoryboardShot).where(StoryboardShot.project_id == project_id)
        )
        for raw in shots:
            session.add(StoryboardShot(
                id=new_id(),
                project_id=project_id,
                idx=int(raw["idx"]),
                title=raw.get("title", ""),
                description=raw.get("description", ""),
                detail=raw.get("detail"),
                duration_sec=raw.get("duration_sec"),
                tags=raw.get("tags"),
                status=StoryboardStatus.PENDING.value,
            ))

        # 推进 stage:draft → storyboard_ready(幂等:若已是 storyboard_ready 跳过)
        if project.stage == ProjectStageRaw.DRAFT.value:
            await advance_stage(session, project, ProjectStageRaw.STORYBOARD_READY)

        await update_job_progress(
            session, job_id, status="succeeded", progress=100,
            total=len(shots), done=len(shots),
        )
        from app.domain.models import Job
        job = await session.get(Job, job_id)
        if job is not None:
            job.result = {"storyboard_count": len(shots)}


@celery_app.task(name="ai.gen_storyboard", bind=True, max_retries=3, default_retry_delay=60)
def gen_storyboard_task(self, job_id: str, project_id: str) -> dict[str, Any]:
    # 与 parse_novel_task 同:只在真实 worker 模式被调用;eager 下改由调用方直接 await _run。
    asyncio.run(_run(job_id, project_id))
    return {"job_id": job_id, "project_id": project_id, "step": "gen_storyboard_done"}
```

- [ ] **Step 5: conftest 里开 ALWAYS_EAGER**

在 `backend/tests/conftest.py` 文件**顶部导入之前**加一行(让 `get_settings` 在 test 环境读到 eager 开关):

```python
import os
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
```

并在 `client` fixture 末尾(`db_module._engine = None` 之前)清 volcano 单例:

```python
    # 每个测试结束都清 volcano client 单例,防止 seed 被前一个测例污染
    from app.infra.volcano_client import reset_volcano_client_for_tests
    reset_volcano_client_for_tests()
    db_module._engine = None
    db_module._session_factory = None
```

- [ ] **Step 6: 冒烟 import**

```bash
cd backend && source .venv/bin/activate && python -c "
from app.tasks.celery_app import celery_app
from app.tasks.ai import parse_novel, gen_storyboard
print([t for t in celery_app.tasks if t.startswith('ai.')])
"
```

Expected: `['ai.gen_storyboard', 'ai.parse_novel', 'ai.ping']`

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/tasks/ backend/tests/conftest.py
git commit -m "feat(backend): Celery ALWAYS_EAGER 开关与 parse_novel/gen_storyboard 任务(走 mock VolcanoClient)"
```

---

## Task 9: Job service + jobs API

**Files:**
- Create: `backend/app/domain/schemas/job.py`
- Modify: `backend/app/domain/schemas/__init__.py`
- Create: `backend/app/domain/services/job_service.py`
- Create: `backend/app/api/jobs.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_jobs_api.py`

- [ ] **Step 1: Pydantic schema**

```python
# backend/app/domain/schemas/job.py
from datetime import datetime

from pydantic import BaseModel


class JobDetail(BaseModel):
    id: str
    kind: str
    project_id: str | None
    target_type: str | None
    target_id: str | None
    status: str
    progress: int
    total: int | None
    done: int
    result: dict | None
    error_msg: str | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
```

更新 `schemas/__init__.py`:

```python
# backend/app/domain/schemas/__init__.py
from .job import JobDetail
from .project import (
    InvalidatedSummary,
    ProjectCreate,
    ProjectDetail,
    ProjectListResponse,
    ProjectRollbackRequest,
    ProjectRollbackResponse,
    ProjectSummary,
    ProjectUpdate,
)

__all__ = [
    "InvalidatedSummary",
    "JobDetail",
    "ProjectCreate",
    "ProjectDetail",
    "ProjectListResponse",
    "ProjectRollbackRequest",
    "ProjectRollbackResponse",
    "ProjectSummary",
    "ProjectUpdate",
]
```

- [ ] **Step 2: Job service**

```python
# backend/app/domain/services/job_service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Job
from app.infra.ulid import new_id


class JobNotFound(Exception):
    pass


class JobService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        kind: str,
        project_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        payload: dict | None = None,
    ) -> Job:
        job = Job(
            id=new_id(),
            kind=kind,
            project_id=project_id,
            target_type=target_type,
            target_id=target_id,
            status="queued",
            progress=0,
            done=0,
            payload=payload,
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get(self, job_id: str) -> Job:
        job = await self.session.get(Job, job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job
```

更新 `services/__init__.py`:

```python
# backend/app/domain/services/__init__.py
from .job_service import JobNotFound, JobService
from .project_service import ProjectNotFound, ProjectService

__all__ = ["JobNotFound", "JobService", "ProjectNotFound", "ProjectService"]
```

- [ ] **Step 3: jobs API + 错误处理补 JobNotFound**

```python
# backend/app/api/jobs.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import ok
from app.deps import get_db
from app.domain.schemas import JobDetail
from app.domain.services import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = JobService(db)
    job = await svc.get(job_id)
    return ok(JobDetail.model_validate(job).model_dump(mode="json"))
```

在 `app/api/errors.py` 里新增 handler(放在 `ProjectNotFound` 的下面):

```python
    @app.exception_handler(JobNotFound)
    async def handle_job_not_found(_: Request, exc: JobNotFound):
        return JSONResponse(fail(40401, "任务不存在"), status_code=404)
```

**别忘了 import**:在 `errors.py` 顶部 import:

```python
from app.domain.services.job_service import JobNotFound
```

- [ ] **Step 4: main.py 挂载**

```python
# backend/app/main.py  (定位到 create_app,追加一行)
from app.api import health, jobs, projects   # 新增 jobs
...
    app.include_router(jobs.router, prefix="/api/v1")
```

- [ ] **Step 5: 集成测试**

```python
# backend/tests/integration/test_jobs_api.py
import pytest

from app.domain.models import Job
from app.infra.ulid import new_id


@pytest.mark.asyncio
async def test_get_job_404(client):
    r = await client.get(f"/api/v1/jobs/{new_id()}")
    assert r.status_code == 404
    assert r.json()["code"] == 40401


@pytest.mark.asyncio
async def test_get_job_ok(client, db_session):
    job = Job(
        id=new_id(),
        kind="parse_novel",
        status="queued",
        progress=0,
        done=0,
    )
    db_session.add(job)
    await db_session.commit()

    r = await client.get(f"/api/v1/jobs/{job.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["id"] == job.id
    assert body["data"]["status"] == "queued"
    assert body["data"]["kind"] == "parse_novel"
```

- [ ] **Step 6: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_jobs_api.py -v
```

Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/domain/schemas/ backend/app/domain/services/ backend/app/api/jobs.py backend/app/api/errors.py backend/app/main.py backend/tests/integration/test_jobs_api.py
git commit -m "feat(backend): JobService 与 GET /api/v1/jobs/{id} 端点"
```

---

## Task 10: Storyboards schema + service + API(列表/新增/编辑/删除/重排/确认)

**Files:**
- Create: `backend/app/domain/schemas/storyboard.py`
- Modify: `backend/app/domain/schemas/__init__.py`
- Create: `backend/app/domain/services/storyboard_service.py`
- Modify: `backend/app/domain/services/__init__.py`
- Create: `backend/app/api/storyboards.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_storyboards_api.py`

- [ ] **Step 1: Schemas**

```python
# backend/app/domain/schemas/storyboard.py
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class StoryboardCreate(BaseModel):
    title: str = Field(default="", max_length=128)
    description: str = Field(default="", min_length=0)
    detail: str | None = None
    duration_sec: float | None = Field(default=None, ge=0, le=300)
    tags: list[str] | None = None
    idx: int | None = Field(default=None, ge=1, le=999)  # None 表示追加到末尾


class StoryboardUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    description: str | None = None
    detail: str | None = None
    duration_sec: float | None = Field(default=None, ge=0, le=300)
    tags: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        # 与 ProjectUpdate 同规则
        if not isinstance(data, dict):
            return data
        for field in ("title", "description", "duration_sec", "tags"):
            if field in data and data[field] is None:
                raise ValueError(f"{field} 不允许显式为 null")
        # detail 允许显式 null(用户可能想清空)
        return data


class StoryboardDetail(BaseModel):
    id: str
    idx: int
    title: str
    description: str
    detail: str | None
    duration_sec: float | None
    tags: list[str] | None
    status: str
    scene_id: str | None
    current_render_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryboardReorderRequest(BaseModel):
    ordered_ids: list[str] = Field(..., min_length=1)


class StoryboardReorderResponse(BaseModel):
    reordered: int
```

更新 `schemas/__init__.py`(追加 storyboard 的导出):

```python
from .storyboard import (
    StoryboardCreate,
    StoryboardDetail,
    StoryboardReorderRequest,
    StoryboardReorderResponse,
    StoryboardUpdate,
)
```

并把它们加入 `__all__`。

- [ ] **Step 2: Service(所有写路径先调 `assert_storyboard_editable`)**

```python
# backend/app/domain/services/storyboard_service.py
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Project, StoryboardShot
from app.domain.schemas.storyboard import StoryboardCreate, StoryboardUpdate
from app.infra.ulid import new_id
from app.pipeline import (
    ProjectStageRaw,
    advance_stage,
    assert_storyboard_editable,
)
from app.pipeline.storyboard_states import StoryboardStatus


class StoryboardNotFound(Exception):
    pass


class StoryboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, project_id: str) -> list[StoryboardShot]:
        stmt = (
            select(StoryboardShot)
            .where(StoryboardShot.project_id == project_id)
            .order_by(StoryboardShot.idx.asc())
        )
        return list((await self.session.scalars(stmt)).all())

    async def _get(self, project_id: str, shot_id: str) -> StoryboardShot:
        stmt = select(StoryboardShot).where(
            StoryboardShot.project_id == project_id,
            StoryboardShot.id == shot_id,
        )
        shot = (await self.session.scalars(stmt)).one_or_none()
        if shot is None:
            raise StoryboardNotFound(shot_id)
        return shot

    async def create(
        self, project: Project, payload: StoryboardCreate
    ) -> StoryboardShot:
        assert_storyboard_editable(project)
        if payload.idx is None:
            max_idx = await self.session.scalar(
                select(func.max(StoryboardShot.idx)).where(
                    StoryboardShot.project_id == project.id
                )
            )
            new_idx = (max_idx or 0) + 1
        else:
            new_idx = payload.idx
            # 把 idx >= new_idx 的全部下移(避免 UNIQUE 冲突),用两阶段:先加大偏移再回落
            # 简化 MVP:直接 +1000 再 -1000+1
            await self.session.execute(
                __import__("sqlalchemy").update(StoryboardShot)
                .where(
                    StoryboardShot.project_id == project.id,
                    StoryboardShot.idx >= new_idx,
                )
                .values(idx=StoryboardShot.idx + 1000)
            )
            await self.session.execute(
                __import__("sqlalchemy").update(StoryboardShot)
                .where(
                    StoryboardShot.project_id == project.id,
                    StoryboardShot.idx >= new_idx + 1000,
                )
                .values(idx=StoryboardShot.idx - 999)
            )

        shot = StoryboardShot(
            id=new_id(),
            project_id=project.id,
            idx=new_idx,
            title=payload.title,
            description=payload.description,
            detail=payload.detail,
            duration_sec=payload.duration_sec,
            tags=payload.tags,
            status=StoryboardStatus.PENDING.value,
        )
        self.session.add(shot)
        await self.session.flush()
        await self.session.refresh(shot)
        return shot

    async def update(
        self, project: Project, shot_id: str, payload: StoryboardUpdate
    ) -> StoryboardShot:
        assert_storyboard_editable(project)
        shot = await self._get(project.id, shot_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(shot, field, value)
        return shot

    async def delete(self, project: Project, shot_id: str) -> None:
        assert_storyboard_editable(project)
        shot = await self._get(project.id, shot_id)
        removed_idx = shot.idx
        await self.session.delete(shot)
        await self.session.flush()
        # 删除后重排后续 idx,避免 1,3,4 这种空洞(前端"镜头 XX"按 idx 显示会跳号)
        await self.session.execute(
            __import__("sqlalchemy").update(StoryboardShot)
            .where(
                StoryboardShot.project_id == project.id,
                StoryboardShot.idx > removed_idx,
            )
            .values(idx=StoryboardShot.idx - 1)
        )

    async def reorder(self, project: Project, ordered_ids: list[str]) -> int:
        assert_storyboard_editable(project)
        shots = await self.list(project.id)
        id_to_shot = {s.id: s for s in shots}
        if len(ordered_ids) != len(id_to_shot) or set(ordered_ids) != set(id_to_shot.keys()):
            raise ValueError("ordered_ids 必须正好包含当前项目下全部分镜 id(无重复无遗漏)")
        # 两阶段避免 UNIQUE 冲突
        for s in shots:
            s.idx = s.idx + 10000
        await self.session.flush()
        for new_idx, sid in enumerate(ordered_ids, start=1):
            id_to_shot[sid].idx = new_idx
        await self.session.flush()
        return len(ordered_ids)

    async def confirm(self, project: Project) -> Project:
        """把 storyboard_ready → characters_locked 的下一阶段推进占位:
        M2 只在 stage=draft 时尝试前进到 storyboard_ready(一般 parse 流程已推进,
        这里是纯手工兜底);若已 >= storyboard_ready 则直接 200 幂等。
        从 storyboard_ready 推进到 characters_locked 需要 M3a 有角色数据后再实现,
        当前 M2 的 confirm 端点只保证「分镜列表有内容且 stage 至少 storyboard_ready」。
        """
        if project.stage == ProjectStageRaw.DRAFT.value:
            count = await self.session.scalar(
                select(func.count(StoryboardShot.id)).where(
                    StoryboardShot.project_id == project.id
                )
            )
            if not count:
                raise ValueError("当前没有分镜,无法确认")
            await advance_stage(self.session, project, ProjectStageRaw.STORYBOARD_READY)
        return project
```

更新 `services/__init__.py` 导出 `StoryboardNotFound` / `StoryboardService`。

- [ ] **Step 3: API**

```python
# backend/app/api/storyboards.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import ok
from app.api.errors import ApiError
from app.deps import get_db
from app.domain.schemas import (
    StoryboardCreate,
    StoryboardDetail,
    StoryboardReorderRequest,
    StoryboardReorderResponse,
    StoryboardUpdate,
)
from app.domain.services import ProjectService, StoryboardService

router = APIRouter(prefix="/projects/{project_id}/storyboards", tags=["storyboards"])


@router.get("")
async def list_storyboards(project_id: str, db: AsyncSession = Depends(get_db)):
    psvc = ProjectService(db)
    await psvc.get(project_id)  # 404 覆盖
    svc = StoryboardService(db)
    shots = await svc.list(project_id)
    return ok([StoryboardDetail.model_validate(s).model_dump(mode="json") for s in shots])


@router.post("", status_code=200)
async def create_storyboard(
    project_id: str, payload: StoryboardCreate, db: AsyncSession = Depends(get_db)
):
    psvc = ProjectService(db)
    project = await psvc.get(project_id)
    svc = StoryboardService(db)
    shot = await svc.create(project, payload)
    return ok(StoryboardDetail.model_validate(shot).model_dump(mode="json"))


@router.patch("/{shot_id}")
async def update_storyboard(
    project_id: str,
    shot_id: str,
    payload: StoryboardUpdate,
    db: AsyncSession = Depends(get_db),
):
    psvc = ProjectService(db)
    project = await psvc.get(project_id)
    svc = StoryboardService(db)
    shot = await svc.update(project, shot_id, payload)
    return ok(StoryboardDetail.model_validate(shot).model_dump(mode="json"))


@router.delete("/{shot_id}")
async def delete_storyboard(
    project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)
):
    psvc = ProjectService(db)
    project = await psvc.get(project_id)
    svc = StoryboardService(db)
    await svc.delete(project, shot_id)
    return ok({"deleted": True})


@router.post("/reorder")
async def reorder_storyboards(
    project_id: str,
    payload: StoryboardReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    psvc = ProjectService(db)
    project = await psvc.get(project_id)
    svc = StoryboardService(db)
    try:
        n = await svc.reorder(project, payload.ordered_ids)
    except ValueError as e:
        raise ApiError(40001, str(e), http_status=422) from e
    return ok(StoryboardReorderResponse(reordered=n).model_dump())


@router.post("/confirm")
async def confirm_storyboards(project_id: str, db: AsyncSession = Depends(get_db)):
    psvc = ProjectService(db)
    project = await psvc.get(project_id)
    svc = StoryboardService(db)
    try:
        await svc.confirm(project)
    except ValueError as e:
        raise ApiError(40901, str(e), http_status=409) from e
    return ok({"stage": project.stage, "stage_raw": project.stage})
```

补一个 `StoryboardNotFound` 的全局 handler(追加到 `errors.py`):

```python
from app.domain.services.storyboard_service import StoryboardNotFound

    @app.exception_handler(StoryboardNotFound)
    async def handle_storyboard_not_found(_: Request, exc: StoryboardNotFound):
        return JSONResponse(fail(40401, "分镜不存在"), status_code=404)
```

main.py include:

```python
from app.api import health, jobs, projects, storyboards
    app.include_router(storyboards.router, prefix="/api/v1")
```

- [ ] **Step 4: 集成测试**

```python
# backend/tests/integration/test_storyboards_api.py
import pytest
from sqlalchemy import update

from app.domain.models import Project, StoryboardShot
from app.pipeline.storyboard_states import StoryboardStatus


async def _create_project_with_shots(client, db_session, stage: str = "draft"):
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s"})
    pid = r.json()["data"]["id"]
    await db_session.execute(update(Project).where(Project.id == pid).values(stage=stage))
    # 种 3 条分镜
    for i in range(1, 4):
        db_session.add(StoryboardShot(
            project_id=pid, idx=i, title=f"t{i}", description="",
            status=StoryboardStatus.PENDING.value,
        ))
    await db_session.commit()
    return pid


@pytest.mark.asyncio
async def test_list_storyboards_empty(client):
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s"})
    pid = r.json()["data"]["id"]
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    assert r.status_code == 200
    assert r.json()["data"] == []


@pytest.mark.asyncio
async def test_list_storyboards_ordered(client, db_session):
    pid = await _create_project_with_shots(client, db_session)
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    data = r.json()["data"]
    assert [s["idx"] for s in data] == [1, 2, 3]


@pytest.mark.asyncio
async def test_create_storyboard_appends_to_tail(client, db_session):
    pid = await _create_project_with_shots(client, db_session)
    r = await client.post(f"/api/v1/projects/{pid}/storyboards", json={
        "title": "新镜", "description": "…",
    })
    assert r.status_code == 200
    assert r.json()["data"]["idx"] == 4


@pytest.mark.asyncio
async def test_create_storyboard_at_position(client, db_session):
    pid = await _create_project_with_shots(client, db_session)
    r = await client.post(f"/api/v1/projects/{pid}/storyboards", json={
        "title": "插入", "description": "", "idx": 2,
    })
    assert r.status_code == 200
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    titles = [s["title"] for s in r.json()["data"]]
    assert titles == ["t1", "插入", "t2", "t3"]


@pytest.mark.asyncio
async def test_edit_storyboard_ok_in_draft(client, db_session):
    pid = await _create_project_with_shots(client, db_session)
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    sid = r.json()["data"][0]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}/storyboards/{sid}",
                           json={"title": "改后"})
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "改后"


@pytest.mark.asyncio
async def test_edit_denied_after_characters_locked(client, db_session):
    pid = await _create_project_with_shots(client, db_session, stage="characters_locked")
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    sid = r.json()["data"][0]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}/storyboards/{sid}",
                           json={"title": "改后"})
    assert r.status_code == 403
    assert r.json()["code"] == 40301


@pytest.mark.asyncio
async def test_delete_storyboard_ok(client, db_session):
    pid = await _create_project_with_shots(client, db_session)
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    sid = r.json()["data"][0]["id"]
    r = await client.delete(f"/api/v1/projects/{pid}/storyboards/{sid}")
    assert r.json()["data"]["deleted"] is True
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    assert len(r.json()["data"]) == 2


@pytest.mark.asyncio
async def test_reorder_storyboards(client, db_session):
    pid = await _create_project_with_shots(client, db_session)
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    ids = [s["id"] for s in r.json()["data"]]
    reversed_ids = list(reversed(ids))
    r = await client.post(f"/api/v1/projects/{pid}/storyboards/reorder",
                          json={"ordered_ids": reversed_ids})
    assert r.json()["data"]["reordered"] == 3
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    assert [s["id"] for s in r.json()["data"]] == reversed_ids


@pytest.mark.asyncio
async def test_reorder_rejects_missing_ids(client, db_session):
    pid = await _create_project_with_shots(client, db_session)
    r = await client.post(f"/api/v1/projects/{pid}/storyboards/reorder",
                          json={"ordered_ids": ["bogus"]})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_confirm_draft_advances_stage(client, db_session):
    pid = await _create_project_with_shots(client, db_session, stage="draft")
    r = await client.post(f"/api/v1/projects/{pid}/storyboards/confirm")
    assert r.status_code == 200
    # 再次读详情确认 stage
    r = await client.get(f"/api/v1/projects/{pid}")
    assert r.json()["data"]["stage_raw"] == "storyboard_ready"


@pytest.mark.asyncio
async def test_confirm_without_storyboards_conflict(client):
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s"})
    pid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/projects/{pid}/storyboards/confirm")
    assert r.status_code == 409
    assert r.json()["code"] == 40901
```

- [ ] **Step 5: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_storyboards_api.py -v
```

Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/schemas/ backend/app/domain/services/ backend/app/api/storyboards.py backend/app/api/errors.py backend/app/main.py backend/tests/integration/test_storyboards_api.py
git commit -m "feat(backend): storyboards CRUD / reorder / confirm 端点(编辑窗口经 pipeline 守门)"
```

---

## Task 11: POST /projects/{id}/parse 触发解析链

**Files:**
- Modify: `backend/app/api/projects.py`
- Create: `backend/tests/integration/test_parse_flow.py`

- [ ] **Step 1: API 扩展**

在 `backend/app/api/projects.py` 顶部追加 import:

```python
from app.api.errors import ApiError
from app.config import get_settings
from app.domain.services import JobService
from app.pipeline import ProjectStageRaw
from app.tasks.ai.parse_novel import _run as _parse_run, parse_novel_task
```

在文件末尾追加:

```python
@router.post("/{project_id}/parse")
async def parse_project(project_id: str, db: AsyncSession = Depends(get_db)):
    psvc = ProjectService(db)
    project = await psvc.get(project_id)
    if project.stage != ProjectStageRaw.DRAFT.value:
        raise ApiError(
            40301,
            f"仅 draft 阶段可触发 parse,当前 stage={project.stage}",
            http_status=403,
        )

    jsvc = JobService(db)
    job = await jsvc.create(
        kind="parse_novel",
        project_id=project.id,
        target_type="project",
        target_id=project.id,
        payload={"story_len": len(project.story or "")},
    )

    # commit 当前事务,否则后续任务在新事务里查不到刚创建的 job / 看不到项目最新状态
    await db.commit()

    # eager 模式下直接在当前事件循环 await 协程,避免 asyncio.run 嵌套导致
    # "RuntimeError: asyncio.run() cannot be called from a running event loop"。
    # worker 模式下走标准 Celery 分发。
    if get_settings().celery_task_always_eager:
        await _parse_run(job.id, project.id)
    else:
        parse_novel_task.apply_async(args=[job.id, project.id])

    return ok({"job_id": job.id})
```

- [ ] **Step 2: 集成测试**

```python
# backend/tests/integration/test_parse_flow.py
import pytest


@pytest.mark.asyncio
async def test_parse_end_to_end_via_mock(client):
    # 1) 创建项目
    r = await client.post("/api/v1/projects", json={
        "name": "冒烟", "story": "皇城夜雨..." * 30,
    })
    pid = r.json()["data"]["id"]

    # 2) 触发 parse(ALWAYS_EAGER 下一次请求内跑完 parse + gen_storyboard)
    r = await client.post(f"/api/v1/projects/{pid}/parse")
    assert r.status_code == 200
    job_id = r.json()["data"]["job_id"]

    # 3) 查 job → 已 succeeded
    r = await client.get(f"/api/v1/jobs/{job_id}")
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "succeeded", body["data"]
    assert body["data"]["progress"] == 100
    assert body["data"]["result"]["storyboard_count"] >= 6

    # 4) 项目 stage 已推进到 storyboard_ready,summary/parsed_stats/overview 已写入
    r = await client.get(f"/api/v1/projects/{pid}")
    data = r.json()["data"]
    assert data["stage_raw"] == "storyboard_ready"
    assert data["summary"]
    assert len(data["parsedStats"]) >= 1
    assert data["projectOverview"]

    # 5) storyboards 数组有数据
    r = await client.get(f"/api/v1/projects/{pid}/storyboards")
    shots = r.json()["data"]
    assert 6 <= len(shots) <= 14
    for i, s in enumerate(shots, 1):
        assert s["idx"] == i
        assert s["status"] == "pending"


@pytest.mark.asyncio
async def test_parse_rejected_outside_draft(client, db_session):
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s"})
    pid = r.json()["data"]["id"]
    # 手工推到 storyboard_ready
    from sqlalchemy import update
    from app.domain.models import Project
    await db_session.execute(update(Project).where(Project.id == pid).values(stage="storyboard_ready"))
    await db_session.commit()

    r = await client.post(f"/api/v1/projects/{pid}/parse")
    assert r.status_code == 403
    assert r.json()["code"] == 40301


@pytest.mark.asyncio
async def test_parse_404_for_unknown_project(client):
    r = await client.post("/api/v1/projects/01H0000000000000000000NOPE/parse")
    assert r.status_code == 404
```

- [ ] **Step 3: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_parse_flow.py -v
```

Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/projects.py backend/tests/integration/test_parse_flow.py
git commit -m "feat(backend): POST /projects/{id}/parse 触发 parse_novel→gen_storyboard(mock)链路"
```

---

## Task 12: 聚合详情拼装 — GET /projects/{id} 真实填 storyboards / queue / progress

**Files:**
- Create: `backend/app/domain/services/aggregate_service.py`
- Modify: `backend/app/domain/services/__init__.py`
- Modify: `backend/app/api/projects.py`

- [ ] **Step 1: AggregateService**

```python
# backend/app/domain/services/aggregate_service.py
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Character, Project, Scene, StoryboardShot
from app.domain.schemas import ProjectDetail
from app.domain.services.project_service import ProjectService
from app.pipeline.storyboard_states import StoryboardStatus


def _map_queue_status(raw: str) -> str:
    """spec §13.1 RenderQueueItem.status:
    succeeded|locked → success, generating → processing, failed|pending → warning"""
    if raw in (StoryboardStatus.SUCCEEDED.value, StoryboardStatus.LOCKED.value):
        return "success"
    if raw == StoryboardStatus.GENERATING.value:
        return "processing"
    return "warning"


class AggregateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_detail(self, project: Project) -> ProjectDetail:
        shots = list(
            (await self.session.scalars(
                select(StoryboardShot)
                .where(StoryboardShot.project_id == project.id)
                .order_by(StoryboardShot.idx.asc())
            )).all()
        )
        char_count = await self.session.scalar(
            select(func.count(Character.id)).where(Character.project_id == project.id)
        )
        scene_count = await self.session.scalar(
            select(func.count(Scene.id)).where(Scene.project_id == project.id)
        )
        # M2 不生成 characters/scenes 数据,所以列表空;count 仍展示
        _ = char_count, scene_count

        total = len(shots)
        succeeded = sum(
            1 for s in shots
            if s.status in (StoryboardStatus.SUCCEEDED.value, StoryboardStatus.LOCKED.value)
        )

        storyboards = [
            {
                "id": s.id,
                "index": s.idx,
                "title": s.title,
                "description": s.description,
                "detail": s.detail or "",
                "duration": f"{float(s.duration_sec)} 秒" if s.duration_sec is not None else "",
                "tags": s.tags or [],
            }
            for s in shots
        ]

        queue = [
            {
                "id": s.id,
                "title": f"镜头 {s.idx:02d}",
                "summary": s.title,
                "status": _map_queue_status(s.status),
            }
            for s in shots
        ]

        return ProjectDetail(
            id=project.id,
            name=project.name,
            stage=ProjectService.stage_zh(project.stage),
            stage_raw=project.stage,
            genre=project.genre,
            ratio=f"{project.ratio} 竖屏" if project.ratio else "",
            suggestedShots=(
                f"建议镜头数 {project.suggested_shots}" if project.suggested_shots else ""
            ),
            story=project.story,
            summary=project.summary or "",
            parsedStats=project.parsed_stats or [],
            setupParams=project.setup_params or [],
            projectOverview=project.overview or "",
            storyboards=storyboards,
            characters=[],  # M3a
            scenes=[],      # M3a
            generationProgress=f"{succeeded} / {total} 已完成",
            generationNotes={"input": "", "suggestion": ""},
            generationQueue=queue,
            exportConfig=[],     # M4
            exportDuration=(
                f"预计成片时长:{sum(float(s.duration_sec or 0) for s in shots):.1f} 秒"
                if shots else ""
            ),
            exportTasks=[],      # M4
        )
```

更新 `services/__init__.py` 导出 `AggregateService`。

- [ ] **Step 2: projects.py 用 AggregateService**

替换 `get_project` 和 `update_project` 里 `_to_detail(...)` 的调用为:

```python
# backend/app/api/projects.py(get_project / update_project / rollback 同改)
from app.domain.services import AggregateService  # 顶部 import 追加

@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.get(project_id)
    detail = await AggregateService(db).build_detail(project)
    return ok(detail.model_dump(mode="json"))


@router.patch("/{project_id}")
async def update_project(
    project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    svc = ProjectService(db)
    project = await svc.update(project_id, payload)
    detail = await AggregateService(db).build_detail(project)
    return ok(detail.model_dump(mode="json"))
```

**删掉** `_to_detail()` 辅助函数(已被 AggregateService 取代);`_to_summary` 保留(列表仍用它)。

- [ ] **Step 3: 增补聚合详情回归测试**

追加到 `backend/tests/integration/test_projects_api.py`:

```python
@pytest.mark.asyncio
async def test_detail_aggregate_with_storyboards(client):
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s" * 100})
    pid = r.json()["data"]["id"]
    await client.post(f"/api/v1/projects/{pid}/parse")

    r = await client.get(f"/api/v1/projects/{pid}")
    data = r.json()["data"]
    assert data["stage_raw"] == "storyboard_ready"
    assert len(data["storyboards"]) >= 6
    sb0 = data["storyboards"][0]
    assert set(sb0.keys()) >= {"id", "index", "title", "description", "detail", "duration", "tags"}
    assert len(data["generationQueue"]) == len(data["storyboards"])
    assert "待" in data["generationProgress"] or "/" in data["generationProgress"]
    assert data["exportDuration"].startswith("预计成片时长")
```

- [ ] **Step 4: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_projects_api.py tests/integration/test_parse_flow.py -v
```

Expected: 原有测试 + 新 1 个 全部 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/services/aggregate_service.py backend/app/domain/services/__init__.py backend/app/api/projects.py backend/tests/integration/test_projects_api.py
git commit -m "feat(backend): AggregateService 聚合详情,GET /projects/{id} 拼 storyboards/generationQueue/progress"
```

---

## Task 13: CORS 中间件

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/.env.example`
- Create: `backend/tests/integration/test_cors.py`

- [ ] **Step 1: config 加 CORS origins**

在 `Settings` 类里追加:

```python
    backend_cors_origins: str = ""  # 逗号分隔,空则不装 CORS 中间件

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]
```

- [ ] **Step 2: main.py 装中间件**

```python
# backend/app/main.py(create_app 里,register_handlers 之前加)
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
    ...
    settings = get_settings()
    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
```

- [ ] **Step 3: .env.example 追加**

```
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

- [ ] **Step 4: 测试**

```python
# backend/tests/integration/test_cors.py
import pytest


@pytest.mark.asyncio
async def test_cors_allows_dev_origin(client, monkeypatch):
    # 前置:client fixture 在创建 app 时已读配置;用 monkeypatch 重建
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
    # 清 get_settings 缓存
    from app.config import get_settings
    get_settings.cache_clear()
    # 重建 app
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.options(
            "/api/v1/projects",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    get_settings.cache_clear()
```

- [ ] **Step 5: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_cors.py -v
```

Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/main.py backend/.env.example backend/tests/integration/test_cors.py
git commit -m "feat(backend): 可配置 CORS 白名单(BACKEND_CORS_ORIGINS),打通前端本地联调(M1 review Low)"
```

---

## Task 14: 级联删除集成测试(delete project → 清 jobs/storyboards)

**Files:**
- Create: `backend/tests/integration/test_project_delete_cascade.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/integration/test_project_delete_cascade.py
import pytest
from sqlalchemy import select

from app.domain.models import Job, Project, StoryboardShot
from app.infra.ulid import new_id


@pytest.mark.asyncio
async def test_delete_project_cascades_jobs_and_storyboards(client, db_session):
    # 用 parse 端点在 project 下创建一个 job,同时生成 storyboards
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s" * 100})
    pid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/projects/{pid}/parse")
    job_id = r.json()["data"]["job_id"]

    # 再手工加一条 project-bound job 确保级联确实清 jobs 表
    extra_job = Job(id=new_id(), kind="render_shot", project_id=pid, status="queued",
                    progress=0, done=0)
    db_session.add(extra_job)
    await db_session.commit()

    # 确认存在
    shots_before = (await db_session.execute(
        select(StoryboardShot).where(StoryboardShot.project_id == pid)
    )).scalars().all()
    jobs_before = (await db_session.execute(
        select(Job).where(Job.project_id == pid)
    )).scalars().all()
    assert len(shots_before) >= 6
    assert len(jobs_before) >= 2

    # 删 project
    r = await client.delete(f"/api/v1/projects/{pid}")
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True

    # FK CASCADE 应清空 jobs + storyboards
    shots_after = (await db_session.execute(
        select(StoryboardShot).where(StoryboardShot.project_id == pid)
    )).scalars().all()
    jobs_after = (await db_session.execute(
        select(Job).where(Job.project_id == pid)
    )).scalars().all()
    proj = (await db_session.execute(
        select(Project).where(Project.id == pid)
    )).scalars().one_or_none()

    assert proj is None
    assert shots_after == []
    assert jobs_after == []


@pytest.mark.asyncio
async def test_unrelated_project_jobs_untouched(client, db_session):
    r = await client.post("/api/v1/projects", json={"name": "a", "story": "s"})
    pid_a = r.json()["data"]["id"]
    r = await client.post("/api/v1/projects", json={"name": "b", "story": "s"})
    pid_b = r.json()["data"]["id"]

    db_session.add(Job(id=new_id(), kind="render_shot", project_id=pid_a,
                       status="queued", progress=0, done=0))
    db_session.add(Job(id=new_id(), kind="render_shot", project_id=pid_b,
                       status="queued", progress=0, done=0))
    await db_session.commit()

    await client.delete(f"/api/v1/projects/{pid_a}")

    jobs_b = (await db_session.execute(
        select(Job).where(Job.project_id == pid_b)
    )).scalars().all()
    assert len(jobs_b) == 1
```

- [ ] **Step 2: 跑通**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_project_delete_cascade.py -v
```

Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_project_delete_cascade.py
git commit -m "test(backend): 删除 project 级联清 jobs/storyboards 集成测试(M1 review Medium)"
```

---

## Task 15: Spec 修正 — setup_params 契约统一为 string[]

**Files:**
- Modify: `docs/superpowers/specs/2026-04-20-backend-mvp-design.md`

- [ ] **Step 1: 改 §6.3.1 创建项目示例**

把第 419 行起的对象形式:

```json
"setup_params": {
  "era_style": "古风 / 写意漫感",
  "tone": "冷月青灰 + 朱砂点色",
  "target": "短视频剧情号"
}
```

改为数组形式(与 §13.1 的 `setupParams: string[]` 一致):

```json
"setup_params": [
  "时代视觉:古风 / 写意漫感",
  "色调:冷月青灰 + 朱砂点色",
  "输出目标:短视频剧情号"
]
```

- [ ] **Step 2: 在 §4.1 projects 表 `setup_params` 行的说明里加一句**

定位到 `| setup_params | JSON | 时代/视觉/输出目标 |`,改为:

```
| `setup_params` | JSON | 展示态字符串数组(与 §13.1 `setupParams: string[]` 一对一直出),如 `["时代视觉:古风","色调:冷月青灰 + 朱砂点色","输出目标:短视频剧情号"]`。未来要拆结构化字段再加 VIEW。 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-20-backend-mvp-design.md
git commit -m "docs(spec): setup_params 统一为 string[],与 §13.1 setupParams 契约对齐(M1 review Medium)"
```

---

## Task 16: 冒烟脚本 smoke_m2.sh + README 更新

**Files:**
- Create: `backend/scripts/smoke_m2.sh`
- Modify: `backend/README.md`

- [ ] **Step 1: 冒烟脚本**

```bash
# backend/scripts/smoke_m2.sh
#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}

echo "[1/7] healthz"
curl -fsS "$BASE/healthz" | jq .

echo "[2/7] create project"
PID=$(curl -fsS -X POST "$BASE/api/v1/projects" \
  -H 'Content-Type: application/json' \
  -d '{"name":"M2 冒烟","story":"皇城夜雨,沈昭宁独立废井旁,月色清冷……","genre":"古风","setup_params":["时代视觉:古风","色调:冷月青灰"]}' | jq -r .data.id)
echo "created: $PID"

echo "[3/7] parse"
JOB_ID=$(curl -fsS -X POST "$BASE/api/v1/projects/$PID/parse" | jq -r .data.job_id)
echo "job: $JOB_ID"

echo "[4/7] poll job(最多 30s)"
for i in $(seq 1 30); do
  STATUS=$(curl -fsS "$BASE/api/v1/jobs/$JOB_ID" | jq -r .data.status)
  if [[ "$STATUS" == "succeeded" ]]; then
    echo "job succeeded at tick $i"
    break
  fi
  if [[ "$STATUS" == "failed" ]]; then
    echo "❌ job failed"
    curl -s "$BASE/api/v1/jobs/$JOB_ID" | jq .
    exit 1
  fi
  sleep 1
done

echo "[5/7] project detail"
curl -fsS "$BASE/api/v1/projects/$PID" | jq '.data | {stage, stage_raw, storyboard_count: (.storyboards | length), queue_count: (.generationQueue | length), overview: .projectOverview[0:40]}'

echo "[6/7] storyboards list"
curl -fsS "$BASE/api/v1/projects/$PID/storyboards" | jq '.data | length'

echo "[7/7] delete"
curl -fsS -X DELETE "$BASE/api/v1/projects/$PID" | jq .

echo "✅ M2 smoke passed"
```

```bash
chmod +x backend/scripts/smoke_m2.sh
```

- [ ] **Step 2: README 更新(追加 M2 章节)**

在 `backend/README.md` 文末追加:

```markdown
## M2 新增

### 启动链路

开发时最简:FastAPI + Celery `ALWAYS_EAGER`,不需要单独拉 worker。`.env` 设:

```
CELERY_TASK_ALWAYS_EAGER=true
AI_PROVIDER_MODE=mock
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

要真实异步:

```bash
# 终端 A
uvicorn app.main:app --reload --port 8000

# 终端 B
celery -A app.tasks.celery_app worker -Q ai -c 4 --loglevel=INFO
```

### M2 范围

- POST `/api/v1/projects/{id}/parse` → mock 解析 + 分镜生成
- GET `/api/v1/jobs/{id}` → 前端轮询入口
- `/api/v1/projects/{id}/storyboards` CRUD + `/reorder` + `/confirm`
- `GET /api/v1/projects/{id}` 聚合详情:`storyboards` / `generationQueue` / `generationProgress` / `exportDuration` 真实填充
- `rollback` 级联清 storyboards.scene_id/status/current_render_id + characters.locked + scenes.locked
- 删除 project 级联清 jobs/storyboards/characters/scenes/exports(FK ON DELETE CASCADE)
- CORS 白名单:`BACKEND_CORS_ORIGINS`

### M2 不包含

- 角色/场景资产**生成**(表已建,数据待 M3a)
- 真实火山 API 调用(`AI_PROVIDER_MODE=real` 留 M3a)
- 镜头渲染(M3b/c)、视频导出(M4)
- 断点续跑 / worker crash 恢复(M5)

### 冒烟

```bash
./scripts/smoke_m2.sh
```
```

- [ ] **Step 3: 跑 smoke**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 &
sleep 3
./scripts/smoke_m2.sh
kill %1
```

Expected: 所有步骤 ✅

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/smoke_m2.sh backend/README.md
git commit -m "docs(backend): M2 冒烟脚本与 README 更新"
```

---

## Task 17: DoD 全量跑 + mypy + 补漏

**Files:** 无

- [ ] **Step 1: 全量 pytest**

```bash
cd backend && source .venv/bin/activate && pytest -v --maxfail=1
```

Expected 通过数量:
- unit:M1 原有(ulid 3 + pipeline 6)= 9 + M2 新增(schema 11 + storyboard state 8 + rollback cascade 3 + volcano mock 7)= 38
- integration:M1 原有(projects 6 + rollback 4)= 10 + M2 新增(alembic 2 + jobs 2 + storyboards 10 + parse 3 + projects 额外 5 + delete cascade 2 + cors 1)= 35
- 合计 **约 73 passed**

- [ ] **Step 2: mypy**

```bash
cd backend && source .venv/bin/activate && mypy app
```

Expected: `Success: no issues found in NN source files`

- [ ] **Step 3: ruff lint**

```bash
cd backend && source .venv/bin/activate && ruff check app tests
```

Expected: 无错误(unused import / 长行等)。有问题 `ruff check --fix` 自动修,commit 进一个 `chore: lint` 单独 commit。

- [ ] **Step 4: 手工核对 pipeline 写入唯一性**

```bash
cd backend && source .venv/bin/activate && rg -n 'project\.stage\s*=' app
```

Expected:所有结果都在 `app/pipeline/transitions.py` 里(两处:`advance_stage`、`rollback_stage`)。若其他地方出现,返回 Task 重构。

- [ ] **Step 5: 冒烟**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 &
sleep 3
./scripts/smoke_m2.sh
kill %1
```

- [ ] **Step 6(可选)pyright 或额外静态检查** 不做

---

## 完成标准 (Definition of Done)

- [ ] `pytest -v` 全量通过;覆盖 unit 与 integration 两层;关键新用例:
  - `test_schema_validation`(PATCH null 拒绝、空白 name 拒绝、setup_params dict 拒绝)
  - `test_alembic_migration`(迁移⇄ORM 漂移检测)
  - `test_parse_flow`(parse → job succeeded → storyboards 出来 → stage=storyboard_ready)
  - `test_storyboards_api`(编辑窗口 403、reorder、confirm)
  - `test_project_delete_cascade`(delete 清 jobs + storyboards)
  - `test_rollback_cascade`(storyboards.scene_id/status 清、characters/scenes.locked=false)
- [ ] `alembic upgrade head` 从干净库起能一次到 0002,且 `test_alembic_migration` 绿
- [ ] `mypy app` 通过(M1 review Low)
- [ ] `ruff check app tests` 无错误
- [ ] `./scripts/smoke_m2.sh` 端到端通过
- [ ] `grep -rn 'project\.stage\s*=' app` 结果只出现在 `app/pipeline/transitions.py`
- [ ] `grep -rn 'jobs\..*setattr\|job\.status\s*=' app` 结果只出现在 `app/pipeline/transitions.py`(`update_job_progress`)
- [ ] M1 review 6 条全部解决并附测试:High(PATCH null)/ Medium(setup_params、jobs FK、Alembic 测试)/ Low(CORS、mypy)
- [ ] spec §6.3.1 的 `setup_params` 示例已改为 `string[]`,与 §13.1 一致
- [ ] `backend/README.md` 有 M2 范围与启动说明
- [ ] git 提交历史按 Task 拆分,每个 Task 至少一次 commit

---

## 衔接下一份 plan

- **Backend M3a**(接真实火山 + 角色/场景生成):
  - 新增 `RealVolcanoClient`(openai SDK + HMAC 签名的人像库子客户端),在 `AI_PROVIDER_MODE=real` 时路由
  - 新增 `gen_character_asset` / `gen_scene_asset` Celery 任务
  - API:`/characters/generate` / `/characters/{id}/lock` / `/scenes/generate` / `/scenes/{id}/lock` / `/storyboards/{id}/bind_scene`
  - pipeline 新增 `lock_protagonist`(项目内主角唯一,SELECT FOR UPDATE)、`advance_to_characters_locked` / `advance_to_scenes_locked`
  - 聚合详情填 `characters` / `scenes` 数组
- **Frontend M1**:本 plan 交付后即可并行启动。前端 CORS 已配白名单 + 所有端点已就位(projects / jobs / storyboards / parse / rollback),可直接联调工作台 UI。Vite proxy 留给前端计划自己决定是否开。

---

## 自检(plan 写完后)

- **Spec 覆盖**:spec §15 M2 声明"Pipeline + mock VolcanoClient:小说解析 + 分镜生成(假数据)全流程;前端能走通工作台 UI,前后端字段一对一联调通过"。
  - Pipeline:Task 5 扩展 rollback 级联、editable guard、update_job_progress ✅
  - mock VolcanoClient:Task 7 ✅(chat + image,契约对齐 volcengine-ark-api.md §3/§4)
  - 解析 + 分镜生成:Task 8 / 11 ✅
  - 前端字段一对一:Task 12 AggregateService 按 spec §13.1 拼 storyboards / queue / progress / exportDuration ✅
- **Placeholder 扫描**:全文无 TBD / TODO / "implement later" / "add appropriate X" / "similar to Task N"
- **类型一致性**:
  - `StoryboardStatus` 在 `storyboard_states.py` 定义,`storyboard.py` 模型、`storyboard_service.py`、`aggregate_service.py`、`tasks/ai/gen_storyboard.py` 一致引用 ✅
  - `ProjectStageRaw` 延续 M1 的 7 值 ENUM,`transitions.advance_stage` 只在 `gen_storyboard_task` 里调用 ✅
  - `JobService.create()` 签名与 `tasks/ai/parse_novel.py` 使用方式一致 ✅
  - `AggregateService.build_detail` 的返回字段与 `ProjectDetail` schema 字段集合完全对齐 ✅
- **前后端契约**:`storyboards[].duration` 字符串拼 `"{dur} 秒"`、`generationQueue[].title` 为 `"镜头 XX"`(零填充)、`exportDuration` 前缀 `"预计成片时长:"`,对齐 spec §13.1 映射表 ✅
- **级联清理**:FK ON DELETE CASCADE 覆盖 projects→{jobs, storyboards, characters, scenes, export_tasks} + storyboards→{shot_renders, shot_character_refs} + export_tasks→export_shot_snapshots;`export_shot_snapshots.render_id` 用 RESTRICT 防止误删引用中的 render(spec §4.8 快照语义) ✅
- **火山 API 契约**:mock client 的 `ChatCompletion` / `ImageGeneration` 字段与 volcengine-ark-api.md §3.2 / §4.2 对应;`response_format=json_object` 行为对齐;`image_url` 的 `mock://` 协议在 M3a 切 real 时会替换成真实 24h URL,应用侧必须立刻转存自家 OSS(已在 volcengine-ark-api.md §0.5 硬规则声明),本 plan 不需要落实转存(M3b 才有图片写入)

---

## M2 Review 遗留问题(2026-04-21 验证后发现)

### High — 阻塞 DoD

#### H1. `mypy app` 9 个类型错误(DoD 要求 0)

| 文件 | 行 | 错误 |
|------|----|------|
| `storyboard_service.py` | 16 | 返回值 `StoryboardShot\|None` 与声明 `StoryboardShot` 不兼容 |
| `storyboard_service.py` | 21 | 返回 `None` 与声明 `StoryboardShot` 不兼容 |
| `storyboard_service.py` | 25、35、49 | `assert_storyboard_editable` 入参 `Project\|None` vs `Project` |
| `aggregate_service.py` | 14 | `get_project_detail` 在 project 为 None 时 `return None`，与返回类型 `ProjectDetail` 不兼容 |
| `volcano_client.py` | 94 | `None` 赋值给 `AsyncOpenAI` 类型变量 |
| `volcano_client.py` | 100 | `messages: list[dict]` 与 openai SDK 枚举联合类型不兼容 |
| `transitions.py` | 160 | `in` 右操作数类型不支持 `object` |

**修复方向**：
- `storyboard_service.get()` 返回类型改为 `StoryboardShot | None`；`update_shot` 也改为 `StoryboardShot | None`
- `update_shot` / `reorder` / `delete_shot` 在 `project` 为 None 时先 raise `ApiError(404)`
- `aggregate_service.get_project_detail` 在 project 为 None 时 raise `ApiError(404)` 而非 `return None`
- `RealVolcanoClient.__init__` 将 `self.client` 声明为 `AsyncOpenAI | None`
- `RealVolcanoClient.chat_completions` 中 `messages` 用 `cast` 或改类型注解
- `transitions.py:160` 检查 `in` 表达式的右侧类型（可能是 `Enum` 成员迭代问题）

#### H2. `ruff check app tests` 20 个错误(DoD 要求 0)

17 个可自动修复（未使用 import），3 个需手工处理：

| 文件 | 问题 |
|------|------|
| `aggregate_service.py:22,25` | `characters`、`scenes` 赋值但未使用（F841）— M2 已确认不需要，删掉这两个查询 |
| `parse_novel.py:76` | `future` 赋值但未使用（F841）— 与 Celery eager 竞态缺陷同根，见 M3 |

**修复方向**：`ruff check --fix app tests` 先跑自动修复，再手工删三处 F841。

### Medium — 不阻塞但 DoD 明确要求

#### M1. 缺少 `test_storyboards_api` 集成测试(DoD 明确列出)

DoD 要求：`test_storyboards_api`（编辑窗口 403、reorder、confirm）

**缺失测试**：
- 在 `storyboard_ready` 阶段以外调用 PATCH 应返回 403
- POST `/reorder` 重排后 idx 顺序正确
- 目前无 confirm 接口（spec 有但 Task 10 未实现 `/storyboards/{id}/confirm`）

**修复方向**：新建 `tests/integration/test_storyboards_api.py`，按 TDD 先写失败测试再补实现。

#### M2. 缺少 `test_project_delete_cascade` 集成测试(DoD 明确列出)

DoD 要求：`test_project_delete_cascade`（delete project → 清 jobs + storyboards）

当前 `test_delete_project` 仅验证 HTTP 200，未查 DB 确认级联清除。

**修复方向**：在 `test_projects_api.py` 补一个 `test_project_delete_cascade`：先创项目、插 job + storyboard，DELETE 后 SELECT 验证两者都消失。

#### M3. Celery eager 模式竞态缺陷

`parse_novel.py:76` 在 loop 已运行时走 `asyncio.ensure_future` 但不等待，HTTP 响应返回时任务可能未完成。`test_parse_flow` 用 `asyncio.sleep(0.2)` 打补丁，不可靠。`gen_storyboard.py` 同样问题。

**修复方向**：
```python
@celery_app.task(name="ai.parse_novel")
def parse_novel(project_id: str, job_id: str):
    # Celery worker 里永远没有 running loop，直接 asyncio.run 即可
    # ALWAYS_EAGER 下也是同步调用，loop 未启动
    asyncio.run(_parse_novel_task(project_id, job_id))
```
删掉 `loop.is_running()` 分支，统一用 `asyncio.run`。测试侧删掉 `sleep(0.2)` 改为直接断言。

#### M4. `aggregate_service` 无效 DB 查询

M2 不返回 `characters`、`scenes`，但仍对两张表发 SELECT（与 H2/F841 同一处）。删掉两个查询即可，同时解决 ruff F841。

### Low

#### L1. git 提交历史未按 Task 拆分(DoD 明确要求)

所有 M2 文件仍在 untracked / unstaged 状态，没有任何 M2 commit。DoD 要求每个 Task 至少一次 commit。

**修复方向**：先解决 High/Medium，再按以下分组提交：
1. Task 2/13/15：schema 严格化 + CORS + spec 修正
2. Task 3/6：Alembic 测试 + 0002 迁移
3. Task 4/5：ORM 模型 + pipeline 扩展
4. Task 7/8：VolcanoClient + Celery tasks
5. Task 9/10：JobService + StoryboardService + API
6. Task 11/12：parse 触发 + AggregateService
7. Task 14/16：级联测试 + smoke 脚本
8. Task 17：DoD 全量验证（mypy/ruff 修复后）

#### L2. smoke_m2.sh 未实际运行

服务端 502，无法端到端验证。待 H1/H2 修复、服务启动后补跑。
