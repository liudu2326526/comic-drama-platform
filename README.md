# 漫剧生成平台（Comic Drama Platform）

面向"小说 → 分镜 → 角色/场景 → 镜头渲染 → 成片导出"整条链路的 AI 漫剧生产工作台。后端接入火山引擎 Ark（大模型 / 图像）与火山人像库，资产托管在华为云 OBS；前端为 Vue 3 中后台工作台。

- 后端设计: [`docs/superpowers/specs/2026-04-20-backend-mvp-design.md`](docs/superpowers/specs/2026-04-20-backend-mvp-design.md)
- 前端设计: [`docs/superpowers/specs/2026-04-20-frontend-mvp-design.md`](docs/superpowers/specs/2026-04-20-frontend-mvp-design.md)
- 分里程碑实施计划: [`docs/superpowers/plans/`](docs/superpowers/plans/)（当前已覆盖 M1 / M2 / M3a，以及 M3b 设计与执行计划）

---

## 仓库结构

```
comic-drama-platform/
├── backend/              FastAPI + SQLAlchemy async + Alembic + Celery + Redis + MySQL 8
├── frontend/             Vue 3 + Vite + TypeScript + Pinia + Axios
├── product/              产品层 HTML/CSS 原型（样式 token 来源，已迁至 frontend/src/styles/）
├── docs/
│   ├── superpowers/      specs/（MVP 设计）+ plans/（M1/M2/M3a 任务拆解）
│   ├── huoshan_api/      火山引擎 Ark 接口备忘
│   ├── huawei_api/       华为云 OBS 接口备忘
│   └── integrations/     其它第三方集成资料
├── CLAUDE.md             仓库级工程规约（架构约束 / 常用命令 / 异步任务约束）
└── AGENTS.md             与 CLAUDE.md 同步的仓库级工作规约入口
```

---

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 Web | FastAPI 0.110 + Uvicorn |
| ORM | SQLAlchemy 2.0 async（`asyncmy` 驱动）|
| 迁移 | Alembic 1.13 |
| 任务队列 | Celery 5.3（双队列 `ai` / `video`），Redis 5 作 broker/backend |
| 数据库 | MySQL 8.0（utf8mb4_unicode_ci） |
| AI 能力 | 火山引擎 Ark（Chat / Image）+ 火山人像库（HMAC-SHA256 签名） |
| 对象存储 | 华为云 OBS（`esdk-obs-python`） |
| 前端框架 | Vue 3.5 + TypeScript 5.7 + Vite 6 |
| 前端状态 | Pinia 2 + Vue Router 4 |
| 前端测试 | Vitest 2 + happy-dom + `@vue/test-utils` |

---

## Prompt Skills 参考

项目在“角色设定 / 场景设定 / 分镜工作台 prompt 优化”阶段，当前主要参考以下 3 个 skill：

| Skill | 来源 | 用途 |
|---|---|---|
| `ai-drama-prompt-factory` | [ClawHub](https://clawhub.ai/zhgarylu/ai-drama-prompt-factory) | 作为项目级“短剧提示词工厂”方法论来源，重点参考其“策划 → 设计 → 剧本 → 诊断 → 组装”的分层思路，用于约束项目级统一视觉设定、角色/场景资产定义和提示词组装方式。 |
| `seedance2.0-prompt-skill` | [GitHub](https://github.com/MapleShaw/seedance2.0-prompt-skill) | 作为 Seedance 2.0 的视频/图片提示词工程参考，重点参考其时间戳分镜、长视频分段、一致性控制、镜头语言和首帧/参考图优先的工作流。 |
| `sd2-pe` | [docs/huoshan_api/SKILL.md](docs/huoshan_api/SKILL.md) | 项目内本地 skill，重点参考其“八大核心要素”“多模态素材映射”“拒绝静默修改”“单时间片只保留一种主运镜”等规则，用于提升分镜工作台 prompt 的可控性。 |

当前推荐的使用方式：

- 项目级统一视觉设定：优先参考 `ai-drama-prompt-factory`
- 角色参考图 / 场景母版图：结合 `ai-drama-prompt-factory` 与 `seedance2.0-prompt-skill`
- 分镜工作台 / render-draft：重点参考 `sd2-pe` 与 `seedance2.0-prompt-skill`

这些 skill 不是运行时依赖，但它们是当前 prompt 结构设计和后续优化的重要方法论来源。

---

## 里程碑

| 里程碑 | 主题 | 范围 |
|---|---|---|
| **M1** | 工程骨架 | 项目 CRUD、`/rollback`、阶段状态机、健康检查、Celery 队列骨架；无业务 AI 调用 |
| **M2** | 小说解析 + 分镜编辑 | `/parse` + `gen_storyboard` 任务、分镜 CRUD/Reorder/Confirm；使用 mock VolcanoClient |
| **M3a** | 真实火山 + 资产持久化 | RealVolcanoClient（含指数退避/错误分级）、角色/场景生成与锁定、主角并发锁定（`SELECT FOR UPDATE`）、人像库入库、OBS 持久化链路 |
| **M3b（规划中）** | 镜头渲染 | 单镜头 render draft → 用户确认 → render job → 版本历史 / 选当前 / 锁定最终版 |
| 后续 | 批量镜头 / 导出 | M3c / M4，见 `docs/superpowers/specs/` |

当前已落地的冒烟脚本：`backend/scripts/smoke_m1.sh` / `smoke_m2.sh` / `smoke_m3a.sh`。M3b 的 backend/frontend smoke 已在 plans 中定义，待实现后接入。

---

## 快速开始

### 0. 前置

- Python **3.12**（3.13 与 pinned `pydantic-core==2.16.3` 不兼容）
- Node.js 20+ / npm
- 可访问的 MySQL 8.0、Redis 7
- `jq` + `mysql` 客户端（仅冒烟脚本用）

### 1. 启动后端

```bash
cd backend
cp .env.example .env          # 首次克隆时；按实际环境填 MYSQL_* / REDIS_* / OBS_* / ARK_*
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 建库（业务库 + 测试库必须不同名）
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "
  CREATE DATABASE IF NOT EXISTS $MYSQL_DATABASE      DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE DATABASE IF NOT EXISTS $MYSQL_DATABASE_TEST DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"

alembic upgrade head

# 本地全链路开发：Celery 任务内联跑，无需单独起 worker
CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload --port 8000
```

生产模式需另起 worker：

```bash
celery -A app.tasks.celery_app worker -Q ai    -c 4 --loglevel=info
celery -A app.tasks.celery_app worker -Q video -c 2 --loglevel=info
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev                   # http://127.0.0.1:5173，自动代理 /api /static → :8000
```

### 3. 冒烟联调

```bash
# 后端侧
backend/scripts/smoke_m1.sh                        # /healthz + 项目 CRUD + 非法回退 → 40301
backend/scripts/smoke_m2.sh                        # 小说解析 + 分镜编辑
backend/scripts/smoke_m3a.sh <PROJECT_ID>          # 角色 → 锁定主角 → 场景 → 绑定 → 聚合

# 前端侧（脚本会自行启动/清理 dev server，5173 须空闲）
frontend/scripts/smoke_m1.sh
frontend/scripts/smoke_m2.sh
```

---

## 关键配置（后端 `.env`）

所有 URL 由 `app.config.Settings` 从**组件**变量拼装，**不要**在 `.env` 里直接写 `DATABASE_URL` / `REDIS_URL` / `CELERY_BROKER_URL`。

| 变量 | 必填 | 说明 |
|---|---|---|
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | ✅ | 业务库连接 |
| `MYSQL_DATABASE_TEST` | ✅（跑测试时） | 测试库，**必须与业务库不同名**（测试会 DROP/CREATE/TRUNCATE） |
| `REDIS_HOST` / `REDIS_PORT` | ✅ | Redis 地址 |
| `REDIS_DB` / `REDIS_DB_BROKER` / `REDIS_DB_RESULT` | ⭕ | 分别用于应用缓存 / Celery broker / Celery 结果，默认 `0 / 1 / 2` |
| `AI_PROVIDER_MODE` | ⭕ | `mock`（M2 默认）/ `real`（M3a 必须） |
| `ARK_API_KEY` / `ARK_CHAT_MODEL` / `ARK_IMAGE_MODEL` | M3a ✅ | 火山引擎 Ark 凭据与端点 ID |
| `VOLC_ACCESS_KEY_ID` / `VOLC_SECRET_ACCESS_KEY` | M3a ✅ | 火山人像库 AK/SK，HMAC-SHA256 签名 |
| `OBS_AK` / `OBS_SK` / `OBS_ENDPOINT` / `OBS_BUCKET` / `OBS_PUBLIC_BASE_URL` | M3a ✅ | 华为云 OBS；`OBS_PUBLIC_BASE_URL` 需公网可访问 |
| `CELERY_TASK_ALWAYS_EAGER` | ⭕ | `true` 时任务在当前请求协程内同步执行，便于本地开发 |
| `LOG_LEVEL` | ⭕ | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## 架构要点

### 后端分层（硬性约束）

```
app/api/*            薄路由；只做参数解析/校验与转发
app/domain/schemas/* Pydantic I/O DTO（ProjectRead 与前端 ProjectData 对齐）
app/domain/services/* 业务逻辑；禁止直接改状态机字段
app/domain/models/*  SQLAlchemy ORM（Project/Job/StoryboardShot/Character/Scene/ShotRender/ExportTask）
app/pipeline/        状态机 + stage/job status 的唯一写入者
app/infra/           外部适配器：db / redis / volcano_client / volcano_asset_client / obs_store / asset_store
app/tasks/           Celery app + 任务（ai/*、video/*），按任务名前缀路由
```

**最重要的不变式**：`app/pipeline/transitions.py` 是 `project.stage` 的**唯一写入入口**。所有推进（`advance_*`）、回退（`rollback_stage`）、主角锁定（`lock_protagonist`）都在此实现，并负责级联清理（渲染状态重置、场景/角色解锁）。Service 和 API 层都不得直接赋值 `project.stage`。同理，`update_job_progress` 是 `jobs.status/progress/done/total` 的唯一写入者，并执行 `queued → running → (succeeded|failed|canceled)` 的状态机校验。

### 阶段状态机

```
draft → storyboard_ready → characters_locked → scenes_locked
      → rendering → ready_for_export → exported
```

- 前进：**只允许按顺序推进一阶**
- 回退：允许跳到任意更早阶段，越过的阶段其产物会被级联重置
- 非法跃迁：抛 `InvalidTransition` → HTTP 403，统一错误码 `40301`
- `stage_raw` 是英文枚举，前端据此做 UI 门控；`stage` 中文字段仅用于展示

### 统一响应信封 & 错误码

所有 HTTP 响应结构为 `{"code": int, "message": str, "data": T | null}`。错误码表：

| code | HTTP | 触发 |
|---|---|---|
| `0` | 200 | 成功 |
| `40001` | 422 | 参数校验失败（Pydantic + 手写校验） |
| `40301` | 403 | `InvalidTransition`（stage / job 状态机） |
| `40401` | 404 | `ProjectNotFound` 等领域未找到 |
| `42201` | 4xx | 内容违规（火山内容审核） |
| `50001` | 500 | 未捕获异常兜底 |

非状态机类的可控错误请抛 `ApiError(code, message, http_status)`（见 `app/api/errors.py`）。

### 前端

- `src/api/` 封装 Axios；不得混入 store 逻辑
- `src/store/` Pinia，只放跨页共享状态；页面私有状态留在组件内
- `src/composables/` 业务复用逻辑，其中两个承担阶段同步：
  - `useStageGate` —— 基于后端 `stage_raw` 决定各编辑面板的写按钮是否可点；锁定时的 toast 附带"回退阶段"快捷入口，打开 `StageRollbackModal`
  - `useJobPolling` —— 轮询 `GET /api/v1/jobs/{id}` 驱动异步任务进度
- `src/styles/` 是 CSS 变量/Token 的**唯一**归属（迁自 `product/workbench-demo/`），组件内禁止内联颜色/尺寸
- Vite 配置见 `frontend/vite.config.ts`：开发端口 5173，`/api` 与 `/static` 代理到 `127.0.0.1:8000`

---

## 测试

### 后端

```bash
cd backend
./.venv/bin/pytest -v                                                # 全量（网络 MySQL 下约 5 min）
./.venv/bin/pytest tests/unit/                                       # 单元（无 DB，秒级）
./.venv/bin/pytest tests/integration/test_projects_api.py            # 单文件
./.venv/bin/pytest tests/integration/test_projects_api.py::test_x    # 单用例
ruff check app tests
mypy
```

- `tests/conftest.py` 使用 **Alembic**（而不是 `Base.metadata.create_all`）初始化测试库，以便尽早发现 schema 漂移
- 引擎使用 `NullPool`，规避 session-scoped engine 跨 pytest-asyncio event loop 的 `Future attached to a different loop` 错误
- `client` fixture 覆写 `db._engine`/`_session_factory`，强制 `celery_task_always_eager=True`，并在每个用例结束后 `TRUNCATE` 全部业务表
- 插入后访问 server-default 字段（如 `created_at`）必须先 `await session.refresh(obj)`，否则会 `MissingGreenlet`

### 前端

```bash
cd frontend
npm run test           # vitest 单测
npm run typecheck      # vue-tsc --noEmit
npm run build          # 先 typecheck 再构建
npm run lint
npm run format
```

---

## 文档索引

- `CLAUDE.md` —— 仓库级工程规约（架构约束 / 常用命令 / 测试陷阱）
- `AGENTS.md` —— 与 `CLAUDE.md` 保持同步的 agent 入口说明
- `backend/README.md` —— 后端详细说明（M1/M3a 章节、接口速览、故障排查、提交规约）
- `frontend/README.md` —— 前端 M1/M2/M3a 范围、端点对接矩阵、阶段门生效点
- `frontend/frontend-stack-and-ux.md` —— 前端通用架构方案（与本项目业务解耦）
- `product/comic-drama-product-design.md` —— 产品侧设计稿
- `docs/superpowers/specs/` —— 后端/前端 MVP 设计 Spec
- `docs/superpowers/plans/` —— 各里程碑任务拆解（含 M3b backend/frontend plan）

---

## 提交规约

按里程碑任务粒度提交，commit 前缀格式：

```
feat(backend): <一句话概述>                 (Task N)
test(backend): <一句话概述>                 (Task N)
docs(backend): <一句话概述>                 (Task N)
refactor(backend): <一句话概述>
chore(backend): <一句话概述>
```

历史提交参考 `backend/README.md` 最底部的 M1 提交清单。
