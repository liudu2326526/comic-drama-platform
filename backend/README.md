# Comic Drama Backend — M3a (Real Volcano & Assets)

漫剧生成平台的后端。M3a 里程碑交付了真实火山引擎(Volcengine Ark)接入、人像库(Asset Library)集成、华为云 OBS 存储以及角色/场景资产生成的完整链路。

相关文档:
- 后端设计: [2026-04-20-backend-mvp-design.md](file:///Users/macbook/Documents/trae_projects/comic-drama-platform/docs/superpowers/specs/2026-04-20-backend-mvp-design.md)
- 实施计划: [2026-04-21-backend-m3a-real-volcano-and-assets.md](file:///Users/macbook/Documents/trae_projects/comic-drama-platform/docs/superpowers/plans/2026-04-21-backend-m3a-real-volcano-and-assets.md)

---

## 目录结构 (M3a 新增)

```
backend/
├── app/
│   ├── api/
│   │   ├── characters.py      /projects/{id}/characters (Generate/List/Patch/Lock)
│   │   └── scenes.py          /projects/{id}/scenes (Generate/List/Patch/Lock)
│   ├── domain/
│   │   ├── services/
│   │   │   ├── character_service.py  人像库注册与锁定逻辑
│   │   │   └── scene_service.py      场景绑定与统计逻辑
│   ├── infra/
│   │   ├── volcano_client.py  RealVolcanoClient 支持 Chat/Image 及指数退避重试
│   │   ├── volcano_errors.py  火山 API 错误分类(RateLimit/ContentFilter/etc.)
│   │   ├── volcano_asset_client.py 人像库(HMAC-SHA256 签名)客户端
│   │   ├── obs_store.py       华为云 OBS 上传工具
│   │   └── asset_store.py     资产持久化流程(Download -> Upload -> Cleanup)
│   └── tasks/
│       └── ai/
│           ├── gen_character_asset.py  角色资产生成任务
│           └── gen_scene_asset.py      场景资产生成任务
├── scripts/
│   └── smoke_m3a.sh           M3a 完整链路冒烟脚本
└── tests/
    ├── unit/
    │   ├── test_volcano_errors.py
    │   ├── test_volcano_asset_signature.py
    │   └── test_asset_store.py
    └── integration/
        ├── test_volcano_real_client.py
        └── test_character_concurrency.py (主角并发锁定测试)
```

---

## 快速开始 (M3a 配置)

### 1. 配置 `.env`

M3a 需要配置火山引擎和华为云 OBS 的真实凭据：

```bash
# 火山引擎 Ark AI
ARK_API_KEY=your_api_key
ARK_CHAT_MODEL=ep-xxx
ARK_IMAGE_MODEL=cv-xxx
AI_PROVIDER_MODE=real  # 必须设为 real 才会调用真实接口

# 火山人像库 (Asset API)
VOLC_ACCESS_KEY_ID=your_ak
VOLC_SECRET_ACCESS_KEY=your_sk

# 华为云 OBS
OBS_AK=your_obs_ak
OBS_SK=your_obs_sk
OBS_ENDPOINT=obs.cn-beijing.myhuaweicloud.com
OBS_BUCKET=your_bucket
OBS_PUBLIC_BASE_URL=https://static.your-domain.com
```

### 2. 数据库迁移

```bash
alembic upgrade head
```
M3a 增加了 `character`/`scene`/`storyboard` 的复合索引以优化查询性能。

### 3. 运行测试

```bash
# 统一使用 .venv 环境
./.venv/bin/pytest tests/integration/test_volcano_real_client.py
./.venv/bin/pytest tests/integration/test_character_concurrency.py
```

### 4. 冒烟验证

```bash
./scripts/smoke_m3a.sh <PROJECT_ID>
```
该脚本会执行：推进阶段 -> 生成角色 -> 锁定主角 -> 生成场景 -> 锁定场景 -> 绑定分镜 -> 详情聚合。

---

## M3b Single Shot Rendering

M3b adds `render_shot` for one storyboard shot at a time:

- `POST /api/v1/projects/{project_id}/shots/{shot_id}/render-draft`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/render`
- `GET /api/v1/projects/{project_id}/shots/{shot_id}/renders`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/renders/{render_id}/select`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/lock`

`POST /render-draft` returns backend-selected prompt + references for user confirmation. `POST /render` returns the standard async ack shape:

```json
{ "job_id": "01H...", "sub_job_ids": [] }
```

The created `render_id` is stored in `jobs.payload.render_id` and copied to `jobs.result.render_id` when the task succeeds.

Run smoke after M3a has produced a project at `scenes_locked`:

```bash
CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload --port 8000
./scripts/smoke_m3b.sh <PROJECT_ID> <SHOT_ID>
```

Batch render remains M3c; export remains M4.


## M3a 核心变更

- **异常分级**: 实现了 `VolcanoError` 体系，支持自动重试（针对 429/5xx）和业务错误识别（针对内容违规等）。
- **人像库集成**: 实现了火山人像库的 HMAC-SHA256 签名算法，主角锁定后会自动入库以保证后续视频生成的一致性。
- **并发安全**: 锁定主角操作使用 `SELECT FOR UPDATE` 确保一个项目在并发请求下只能有一个主角。
- **存储优化**: 采用 `Temporary Download -> OBS Upload -> Cleanup` 流程，后端本地不保留长期资产文件。

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
| `40901` | 409 | 业务冲突(如同项目已有进行中的角色/场景生成任务) |
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
