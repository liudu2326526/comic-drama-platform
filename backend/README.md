# Comic Drama Backend — M1

漫剧生成平台的后端骨架。本里程碑交付 FastAPI + SQLAlchemy + Alembic + Celery + Redis + MySQL 完整工程骨架、项目 CRUD、阶段回退(rollback)、健康检查与 jobs 表;所有 AI / 资产生成阶段在 M1 内均**未实现**,统一交给 M2 起的 pipeline 任务。

相关文档:
- 后端设计:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md`
- 实施计划:`docs/superpowers/plans/2026-04-20-backend-m1-skeleton.md`

---

## 目录结构

```
backend/
├── pyproject.toml          setuptools build-backend + 依赖清单(锁死版本)
├── alembic.ini             Alembic 配置,sqlalchemy.url 由 env.py 注入
├── alembic/
│   ├── env.py              async_engine_from_config + Base.metadata
│   └── versions/
│       └── 0001_init_projects_and_jobs.py
├── app/
│   ├── main.py             FastAPI factory + lifespan 日志装配
│   ├── config.py           pydantic-settings,MYSQL_*/REDIS_* 组件拼 URL
│   ├── deps.py             get_db 依赖(session 自动 commit/rollback)
│   ├── api/                薄路由层
│   │   ├── envelope.py     {code, message, data} 信封 + ok/fail 工具
│   │   ├── errors.py       全局异常 handler(ProjectNotFound / InvalidTransition / 校验 / 兜底)
│   │   ├── health.py       /healthz /readyz
│   │   └── projects.py     /api/v1/projects CRUD + /rollback
│   ├── domain/
│   │   ├── models/         Base + Project + Job ORM
│   │   ├── schemas/        Pydantic 入参/出参
│   │   └── services/       纯业务逻辑,不改 stage/status
│   ├── pipeline/           阶段状态机(唯一写 project.stage 的地方)
│   │   ├── states.py       ProjectStageRaw enum + STAGE_ZH + 合法性判定
│   │   └── transitions.py  advance_stage / rollback_stage
│   ├── tasks/              Celery 应用(M1 仅含 ai.ping)
│   ├── infra/              db / redis / ulid 适配层
│   └── utils/logger.py     structlog JSON 日志
├── scripts/smoke_m1.sh     M1 冒烟脚本
├── tests/
│   ├── conftest.py         test_engine + client + db_session + TRUNCATE 隔离
│   ├── unit/               test_ulid / test_pipeline_transitions
│   └── integration/        test_projects_api / test_rollback_api
└── .env.example            组件式环境变量模板
```

架构原则:`api/` 只做薄路由,`domain/services/` 不改状态字段,**所有 `project.stage` 写入必须经过 `pipeline/transitions.py`**。

---

## 快速开始

### 前置条件

- **Python 3.12**(3.13 当前与 `pydantic-core==2.16.3` 不兼容,Rust 扩展构建失败)
- 可访问的 MySQL 8.0 实例与 Redis 7 实例
- `mysql` 客户端与 `jq`(仅冒烟脚本用)

### 1. 配置 `.env`

```bash
cd backend
cp .env.example .env    # 首次克隆时
# 按实际环境填 MYSQL_* 与 REDIS_*
```

关键变量:

| 变量 | 必填 | 说明 |
|---|---|---|
| `MYSQL_HOST` / `MYSQL_PORT` | ✅ | MySQL 地址 |
| `MYSQL_USER` / `MYSQL_PASSWORD` | ✅ | 账号,需对 `MYSQL_DATABASE` 与 `MYSQL_DATABASE_TEST` 有 DDL 权限 |
| `MYSQL_DATABASE` | ✅ | 业务库,默认 `comic_drama` |
| `MYSQL_DATABASE_TEST` | ✅(跑测试时) | 测试库,默认 `comic_drama_test`,**必须与业务库不同**(测试会 DROP/CREATE/TRUNCATE) |
| `REDIS_HOST` / `REDIS_PORT` | ✅ | Redis 地址 |
| `REDIS_DB` / `REDIS_DB_BROKER` / `REDIS_DB_RESULT` | ⭕ | 分别用于应用缓存 / Celery broker / Celery 结果后端,默认 0/1/2 |
| `LOG_LEVEL` | ⭕ | `DEBUG` / `INFO` / `WARNING` / `ERROR`,大小写不敏感 |

> 代码中的 `DATABASE_URL` / `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` 均由 `app.config.Settings` 从上述组件变量计算,**不要**直接在 `.env` 写 URL。

### 2. 虚拟环境

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

安装若因本地 SOCKS 代理报 `socksio` 相关错误,先 `unset all_proxy ALL_PROXY` 再 `pip install`。

### 3. 建库与迁移

```bash
source .env
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "
  CREATE DATABASE IF NOT EXISTS $MYSQL_DATABASE        DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE DATABASE IF NOT EXISTS $MYSQL_DATABASE_TEST   DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"

alembic upgrade head
```

迁移完成后 `SHOW TABLES;` 应含 `projects` / `jobs` / `alembic_version` 三张。

### 4. 启动 API

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. 冒烟验证

```bash
./scripts/smoke_m1.sh
```

覆盖 `/healthz` → 创建 → 读取 → 同阶段回退(预期 403/40301)→ 删除,通过则打印 `✅ smoke passed`。

---

## 测试

```bash
pytest -v
```

- **单元测试**:`tests/unit/` — ULID + pipeline 状态机,无外部依赖
- **集成测试**:`tests/integration/` — 起内存 ASGI app 并直连测试库 `MYSQL_DATABASE_TEST`,每个测例末尾 `TRUNCATE` 所有表以做隔离

由于 NullPool 逐请求新建连接,且测试库走网络(非 docker 本地),全量跑一次约 5 分钟(19 测试)。M1 接受这个开销;M2+ 可切换到 docker 本地 MySQL 提速。

预期结果:

```
19 passed, 2 warnings
  tests/unit/test_pipeline_transitions.py      6 passed
  tests/unit/test_ulid.py                       3 passed
  tests/integration/test_projects_api.py        6 passed
  tests/integration/test_rollback_api.py        4 passed
```

> 2 个 DeprecationWarning 来自 pytest-asyncio 0.23 的 `event_loop` fixture 显式覆盖写法,在 M2 升级到 0.24+ 时按官方指引替换为 `loop_scope` 即可。

---

## API 速览

所有响应包裹统一信封:

```json
{ "code": 0, "message": "ok", "data": <T | null> }
```

| Method | Path | 说明 |
|---|---|---|
| `GET` | `/healthz` | DB + Redis 连通性检查 |
| `GET` | `/readyz` | DB 就绪检查 |
| `POST` | `/api/v1/projects` | 创建项目 |
| `GET` | `/api/v1/projects?page=&page_size=` | 列表 |
| `GET` | `/api/v1/projects/{id}` | 详情(与前端 `ProjectData` 对齐) |
| `PATCH` | `/api/v1/projects/{id}` | 更新 `name`/`genre`/`ratio`/`setup_params` |
| `DELETE` | `/api/v1/projects/{id}` | 删除 |
| `POST` | `/api/v1/projects/{id}/rollback` | 回退到更早 stage,body `{ "to_stage": "draft" }` |

### 错误码

| code | HTTP | 场景 |
|---|---|---|
| `0` | 200 | 成功 |
| `40001` | 422 | 参数校验失败(含 Pydantic 422 与非法 `to_stage`) |
| `40301` | 403 | 当前 stage 不允许该操作(`InvalidTransition`) |
| `40401` | 404 | 资源不存在(`ProjectNotFound`) |
| `50001` | 500 | 未捕获异常兜底 |

### 阶段机(`project.stage`)

7 值英文 ENUM,前端基于 `stage_raw` 做门控,`stage` 中文字段仅用于展示:

```
draft → storyboard_ready → characters_locked → scenes_locked → rendering → ready_for_export → exported
```

推进规则(M1 仅开放 `rollback` 端点,`advance_stage` 在 M2 由 pipeline 触发):
- **前进**仅允许按顺序推进一阶
- **回退**允许跳到任意更早阶段,同阶段与向前均拒绝(`40301`)

中文映射见 `app/pipeline/states.py::STAGE_ZH`,与 spec §13.2 一一对应。

### 样例

```bash
# 创建
curl -s -X POST http://127.0.0.1:8000/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"皇城夜雨","story":"...","genre":"古风","ratio":"9:16"}'

# 详情(同时拿到中文展示值 stage 与英文 stage_raw)
curl -s http://127.0.0.1:8000/api/v1/projects/$PID | jq '.data | {stage, stage_raw, name}'

# 回退(假设已在 rendering 阶段)
curl -s -X POST http://127.0.0.1:8000/api/v1/projects/$PID/rollback \
  -H 'Content-Type: application/json' -d '{"to_stage":"storyboard_ready"}'
```

---

## M1 范围与边界

**包含**:
- FastAPI + SQLAlchemy async + Alembic + Celery + Redis 工程骨架
- `projects` / `jobs` 表(jobs 表仅建表,M1 内无业务写入)
- 项目 CRUD + `/rollback` 端点
- 阶段状态机 + 合法性校验(`pipeline/transitions.py`)
- 健康检查 `/healthz` `/readyz`
- Celery 双队列(`ai` / `video`)路由 + ping 任务
- 19 个 unit + integration 测试

**不包含**(按后续里程碑展开):
- 小说解析、分镜生成、角色/场景资产、镜头渲染、视频导出 — **M2**
- 真实火山 AI 调用 — **M3a**,M2 使用 mock VolcanoClient
- Dockerfile / docker-compose 生产编排 — 见 plan Task 15(已推迟)
- 鉴权、多租户、配额 — MVP 范围外

---

## 故障排查

| 症状 | 原因 / 处理 |
|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | `.venv` 未激活或未安装依赖,重跑 `pip install -e ".[dev]"` |
| `pydantic-core` 构建失败(Rust 相关) | Python 3.13 + pydantic-core 2.16 组合不兼容,切 Python 3.12 重建 venv |
| `pip install` 提示 `socksio not installed` | 本地 SOCKS 代理干扰 pip,`unset all_proxy ALL_PROXY` 后重试 |
| `alembic upgrade head` 报 `Can't locate revision ...` | `alembic_version` 残留其他项目 revision,确认使用**专属**的 `comic_drama` 库,不要复用共享库 |
| 集成测试 `Future attached to a different loop` | conftest 未启用 `NullPool`,检查 `tests/conftest.py::test_engine` |
| 测试中 `created_at` 读取报 MissingGreenlet | 缺少 `session.refresh(project)`,见 `ProjectService.create` |

---

## 提交规约

M1 所有提交按 Task 拆分:

```
d1087f5 feat(backend): 初始化后端工程骨架与依赖清单                (Task 1)
a3e8164 feat(backend): 配置/日志/ULID/redis 客户端基础设施          (Task 2)
f9f57dc test(backend): 修正 ULID 单调性测试                        (Task 2 fix)
1768bee refactor(backend): redis_client 用 functools.cache         (Task 2 polish)
f796bd6 feat(backend): 异步 DB 引擎、session 工厂与 DeclarativeBase (Task 3)
462c1d4 feat(backend): pipeline 阶段 Enum + 跃迁合法性校验单测      (Task 5/1)
b8dcd63 feat(backend): projects/jobs ORM 模型                      (Task 4)
3999ff5 feat(backend): pipeline.transitions 状态写入唯一入口       (Task 5/2)
da5b017 feat(backend): alembic 初始化与 0001 迁移                   (Task 6)
54ac44e feat(backend): 项目 CRUD 与 rollback 的 Pydantic schemas   (Task 7)
6ee3d69 feat(backend): Project service CRUD 与 rollback 转发       (Task 8)
2f0ced2 feat(backend): 响应信封、全局错误 handler、健康检查端点      (Task 9)
8224133 feat(backend): projects CRUD 与 rollback REST 端点         (Task 10)
13c59f6 feat(backend): Celery 应用骨架与 ai/video 队列路由          (Task 11)
e373085 feat(backend): FastAPI 入口装配与路由挂载                  (Task 12)
1bd1a86 test(backend): projects CRUD 集成测试 + TRUNCATE 隔离       (Task 13)
059a2c0 test(backend): rollback 端点集成测试                       (Task 14)
b2fda6d docs(backend): M1 冒烟脚本与 README                        (Task 16)
f647feb chore(backend): .gitignore 覆盖 egg-info / build / dist
```
