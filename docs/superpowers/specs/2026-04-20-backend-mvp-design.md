# 漫剧生成平台 — 后端 MVP 设计文档

> **文档版本**:v1.0 · 2026-04-20
> **范围**:MVP 最小闭环后端(接口 + 数据库 + 异步任务 + 存储)
> **配套**:前端工作台 demo `product/workbench-demo/`、产品文档 `product/comic-drama-product-design.md`

---

## 1. 目标与非目标

### 1.1 目标

跑通产品文档第 9 节定义的 MVP 最小闭环:

> 输入小说 → 自动分镜 → 锁定 1 个主角 → 自动匹配场景模板 → 生成镜头静帧 → 拼接导出短视频

后端在此范围内提供:

- 项目 CRUD、小说解析、分镜生成/编辑
- 角色资产生成与锁定
- 场景资产生成与锁定(含模板)
- 镜头批量/单条生成,版本回退
- 视频合成与导出
- 异步任务进度与断点续跑
- 与前端 demo 数据模型完全对齐的 REST 接口

### 1.2 非目标(本期不做)

- 用户登录/多租户/团队协作
- 配音/字幕/口型/运镜动画
- 多剧集协同、章节连载
- 实时推送(SSE/WebSocket),前端统一轮询
- 多 AI 供应商动态路由
- 付费、计费、配额

---

## 2. 技术选型

| 维度 | 选型 | 备注 |
| --- | --- | --- |
| 语言 | Python 3.11 | |
| Web 框架 | FastAPI 0.110+ | 原生 async、OpenAPI 自动生成 |
| ORM | SQLAlchemy 2.x (async) | 配合 `asyncmy` 驱动 |
| 迁移 | Alembic | |
| 数据库 | MySQL 8.x | 新建库 `comic_drama`,复用 `172.16.7.108:3308` 实例 |
| 任务队列 | Celery 5.x + Redis 7 | Redis 同时承担 broker / result backend / 业务缓存 |
| 对象存储 | 本地文件系统 + Nginx 静态目录 | `/data/assets/...` 经 Nginx 暴露为 `/static/...` |
| AI 供应商 | 字节火山引擎(单供应商) | 封装在 `infra/volcano_client.py`,一处替换 |
| 视频合成 | FFmpeg (subprocess) | Celery `video` worker 独占 |
| 鉴权 | 无(MVP) | 所有接口默认在内网 |
| 部署 | docker-compose | 6 个服务:api / celery-ai / celery-video / mysql / redis / nginx |
| 日志 | structlog + JSON | 统一 stdout,由容器日志驱动收集 |

---

## 3. 代码结构

```
backend/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
├── app/
│   ├── main.py                 # FastAPI 实例 & 依赖装配
│   ├── config.py               # Pydantic Settings
│   ├── deps.py                 # DB session / redis 依赖
│   │
│   ├── api/                    # HTTP 层(薄)
│   │   ├── projects.py
│   │   ├── storyboards.py
│   │   ├── characters.py
│   │   ├── scenes.py
│   │   ├── shots.py
│   │   ├── exports.py
│   │   └── jobs.py
│   │
│   ├── domain/                 # 业务模型、schema、service
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── schemas/            # Pydantic I/O
│   │   └── services/           # 纯业务逻辑,不改 stage/status
│   │
│   ├── pipeline/               # 状态机唯一出入口
│   │   ├── states.py           # 枚举与流转表
│   │   ├── transitions.py      # 所有 stage/status 写入经此
│   │   └── dispatcher.py       # 决定"当前阶段完成后下一步是啥"
│   │
│   ├── tasks/                  # Celery 任务
│   │   ├── celery_app.py
│   │   ├── ai/                 # queue=ai
│   │   │   ├── parse_novel.py
│   │   │   ├── gen_storyboard.py
│   │   │   ├── gen_character.py
│   │   │   ├── gen_scene.py
│   │   │   └── render_shot.py
│   │   └── video/              # queue=video
│   │       └── export_video.py
│   │
│   └── infra/                  # 外部系统适配
│       ├── volcano_client.py
│       ├── storage.py
│       ├── ffmpeg.py
│       └── redis_client.py
│
└── tests/
    ├── unit/
    └── integration/
```

**不变量**:`project.stage` / `shot.status` / `shot_render.status` / `export_task.status` 的**状态迁移**只能经 `pipeline.transitions` 写入。其他 service 与 API 只读,违反即 PR 打回。

> 细化:**新插入行**的初始状态(如 `shot.status='pending'`、`shot_render.status='queued'`、`export_task.status='queued'`)允许 service/task 在 `INSERT` 时直接设置 —— 这属于"造一行",不是"改一行"。一旦该行存在,后续对其 `status` 的任何改写(包括 `rollback_stage` 内的 bulk reset,也包括同一条 row 的阶段推进/失败/锁定)必须走 `pipeline.transitions` 里的函数。这条细化是为了避免把 INSERT 也算违反不变量、被迫为所有建表塞一个 `pipeline.transitions.create_*` 包装函数。

---

## 4. 数据库设计

所有表默认:`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci`。主键统一用 **ULID**(`CHAR(26)`),应用层生成。

### 4.1 `projects` — 项目主表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CHAR(26) PK | ULID |
| `name` | VARCHAR(128) NOT NULL | |
| `stage` | ENUM | 见 §5.1 |
| `genre` | VARCHAR(64) | 古风权谋 / 学院科幻 ... |
| `ratio` | VARCHAR(16) DEFAULT '9:16' | |
| `story` | MEDIUMTEXT NOT NULL | 原始小说正文 |
| `summary` | TEXT | AI 生成的节奏建议 |
| `parsed_stats` | JSON | `["字数 1180","已识别角色 4",…]` |
| `setup_params` | JSON | 时代/视觉/输出目标 |
| `overview` | TEXT | |
| `suggested_shots` | SMALLINT | 系统建议镜头数 |
| `created_at` / `updated_at` | DATETIME | |

### 4.2 `storyboards` — 分镜镜头

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CHAR(26) PK | |
| `project_id` | CHAR(26) FK, INDEX | |
| `idx` | SMALLINT NOT NULL | 镜头序号,项目内唯一 |
| `title` | VARCHAR(128) | |
| `description` | TEXT | 镜头描述 |
| `detail` | TEXT | 运镜/光线等更详细说明 |
| `duration_sec` | DECIMAL(4,1) | |
| `tags` | JSON | `["角色:沈昭宁","场景:冷宫废院",…]` |
| `status` | ENUM | 见 §5.2 |
| `current_render_id` | CHAR(26) NULL FK → `shot_renders.id` | 当前选中版本 |
| `scene_id` | CHAR(26) NULL FK → `scenes.id` | 绑定的场景资产 |
| `created_at` / `updated_at` | DATETIME | |

`UNIQUE (project_id, idx)`

### 4.3 `characters` — 角色资产

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CHAR(26) PK | |
| `project_id` | CHAR(26) FK, INDEX | |
| `name` | VARCHAR(64) | |
| `role_type` | ENUM('protagonist','supporting','atmosphere') | |
| `is_protagonist` | BOOL | 应用层保证项目内最多 1 个 |
| `summary` | VARCHAR(255) | 卡片摘要 |
| `description` | TEXT | 角色描述 string(生成 prompt 用) |
| `meta` | JSON | 主视角/动态特征/一致性约束 |
| `reference_image_url` | VARCHAR(512) | |
| `video_style_ref` | JSON | 视频形象参考 |
| `locked` | BOOL DEFAULT FALSE | 主角确认锁定后置 TRUE |
| `created_at` / `updated_at` | DATETIME | |

### 4.4 `scenes` — 场景资产

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CHAR(26) PK | |
| `project_id` | CHAR(26) FK, INDEX | |
| `name` | VARCHAR(64) | |
| `theme` | VARCHAR(32) | `theme-palace` / `theme-academy` / `theme-harbor` |
| `summary` | VARCHAR(255) | |
| `description` | TEXT | 场景描述 string |
| `meta` | JSON | |
| `reference_image_url` | VARCHAR(512) | |
| `video_style_ref` | JSON | |
| `template_id` | VARCHAR(64) NULL | 若由模板派生,记录模板 key |
| `locked` | BOOL DEFAULT FALSE | |
| `created_at` / `updated_at` | DATETIME | |

### 4.5 `shot_character_refs` — 镜头⇄角色 多对多

| 字段 | 类型 |
| --- | --- |
| `shot_id` | CHAR(26) |
| `character_id` | CHAR(26) |

复合主键 `(shot_id, character_id)`。

### 4.6 `shot_renders` — 镜头生成版本历史

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CHAR(26) PK | |
| `shot_id` | CHAR(26) FK, INDEX | |
| `version_no` | INT | 同一 shot 内自增 |
| `status` | ENUM('queued','running','succeeded','failed') | |
| `prompt_snapshot` | JSON | 本次生成的角色/场景/镜头 prompt 全快照 |
| `image_url` | VARCHAR(512) | 成功时结果 URL |
| `provider_task_id` | VARCHAR(128) | 火山侧任务 ID |
| `error_code` | VARCHAR(64) | |
| `error_msg` | TEXT | |
| `created_at` / `finished_at` | DATETIME | |

`UNIQUE (shot_id, version_no)`

### 4.7 `export_tasks` — 导出任务

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CHAR(26) PK | |
| `project_id` | CHAR(26) FK, INDEX | |
| `name` | VARCHAR(128) | |
| `status` | ENUM('queued','running','succeeded','failed') | |
| `config` | JSON | 分辨率/比例/单镜头时长/转场 |
| `video_url` | VARCHAR(512) | |
| `cover_url` | VARCHAR(512) | |
| `duration_sec` | DECIMAL(6,1) | |
| `progress` | TINYINT | 0-100 |
| `error_msg` | TEXT | |
| `created_at` / `finished_at` | DATETIME | |

### 4.8 `export_shot_snapshots` — 导出的镜头版本快照

| 字段 | 类型 |
| --- | --- |
| `export_task_id` | CHAR(26) FK |
| `shot_id` | CHAR(26) FK |
| `render_id` | CHAR(26) FK → `shot_renders.id` |
| `order_idx` | SMALLINT |

复合主键 `(export_task_id, shot_id)`。**用途**:把"导出那一刻每个镜头引用哪个 render 版本"钉死,后续重生成不影响已成片。

### 4.9 `jobs` — 异步任务业务表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CHAR(26) PK | 前端轮询用 |
| `project_id` | CHAR(26) INDEX | |
| `kind` | ENUM | `parse_novel` / `gen_storyboard` / `gen_character_asset` / `gen_scene_asset` / `render_shot` / `render_batch` / `export_video` |
| `target_type` / `target_id` | VARCHAR(32) / CHAR(26) | 绑定的业务对象 |
| `celery_task_id` | VARCHAR(64) | |
| `status` | ENUM('queued','running','succeeded','failed','canceled') | |
| `progress` | TINYINT | 0-100 |
| `total` / `done` | SMALLINT | 批量任务用 |
| `payload` | JSON | |
| `result` | JSON | |
| `error_msg` | TEXT | |
| `created_at` / `updated_at` / `finished_at` | DATETIME | `updated_at` 由 worker 每次 `update_job_progress` 刷新,§7.4 断点续跑扫描依赖此列;`ON UPDATE CURRENT_TIMESTAMP` |

**字段语义分层提示**:`projects.parsed_stats` / `setup_params` 当前直接存"展示态字符串数组",好处是后端拼装简单、前端零转换。若未来要给移动端或第三方开放,应拆成结构化字段(`word_count` / `identified_character_count` / `era_style` / `tone` / `target` 等)并保留一层 VIEW 渲染为展示串。MVP 不做。

### 4.10 ER 关系总览

```
projects ─┬─< storyboards ─── scene_id >── scenes
          │        │
          │        ├─< shot_renders
          │        └─< shot_character_refs >── characters
          │
          ├─< characters
          ├─< scenes
          └─< export_tasks ─< export_shot_snapshots
                                    │
                                    └── render_id >── shot_renders

jobs ── target_id 软引用到任意业务对象
```

---

## 5. 状态机

### 5.1 `projects.stage`

```
draft
  │  POST /projects/{id}/parse  (parse_novel + gen_storyboard)
  ▼
storyboard_ready
  │  POST /projects/{id}/characters/generate  (gen_character_asset × N)
  │  POST /projects/{id}/characters/{cid}/lock
  ▼
characters_locked
  │  POST /projects/{id}/scenes/generate
  │  POST /projects/{id}/scenes/{sid}/lock
  ▼
scenes_locked
  │  POST /projects/{id}/shots/render        (render_batch)
  ▼
rendering
  │  (所有 shot 都到达 succeeded 或 locked)
  ▼
ready_for_export
  │  POST /projects/{id}/exports
  ▼
exported
```

**编辑窗口规则**(关键不变量,避免"新分镜 + 旧资产"混合导出):

- `stage = draft | storyboard_ready` 时,storyboards 可自由编辑(新增/删除/改文案/重排)
- 进入 `characters_locked` 之后,storyboards 变为**只读**;任何编辑必须先显式调用 `POST /projects/{id}/rollback` 把 stage 回退到 `storyboard_ready`,同一事务内 pipeline 会:
  1. 清空所有 `storyboards.scene_id`
  2. 把所有 `storyboards.status` 置回 `pending`、`current_render_id=NULL`(但 `shot_renders` 历史记录保留,不删行、不删图片文件)
  3. 把 `characters.locked`、`scenes.locked` 全部置 FALSE
  4. 响应里返回"被失效的镜头数 / 角色数 / 场景数"供前端提示用户
- 回退粒度:`rollback` 接受 `to_stage` 参数,只允许回退到**更早**的阶段,不允许跳级推进;非法目标返回 40301
- `exported` 阶段 rollback 不删除已生成的 MP4(成片永远留痕)

### 5.2 `storyboards.status`

```
pending → generating → succeeded → locked
                    └─→ failed ─┘ (可重试)
```

- `succeeded`:有至少一个成功的 `shot_render`,`current_render_id` 指向它
- `locked`:用户在前端点击"锁定为最终版",进入导出前必须处于 `succeeded` 或 `locked`

### 5.3 `shot_renders.status` / `export_tasks.status`

标准四态:`queued → running → succeeded | failed`。

### 5.4 `jobs.status`

`queued → running → succeeded | failed | canceled`。

**不变量**(由 `pipeline/transitions.py` 强制):

1. `storyboards` 的编辑窗口见 §5.1"编辑窗口规则",非法写入抛 `InvalidTransition` → 40301
2. 只有 `stage >= characters_locked` 才能发起场景生成
3. 发起导出前,所有 shot 必须是 `succeeded` 或 `locked`,否则 409 并返回缺失列表
4. `is_protagonist=TRUE` 的角色在项目内最多 1 个:
   - **应用层**:`pipeline.transitions.lock_protagonist(project_id, character_id)` 在事务中 `SELECT ... FOR UPDATE` 该项目的所有角色,清除旧主角后再置新主角,全程串行化
   - **DB 兜底**(可选,MVP 不开启):新增生成列 `protagonist_guard = IF(is_protagonist, project_id, NULL)` + `UNIQUE(protagonist_guard)`。这是 MySQL 8 能达到的最接近 partial unique 的写法;MVP 先不上以避免迁移复杂度,后期如发现应用层锁不住再加

---

## 6. API 设计

### 6.1 通用约定

- Base path:`/api/v1`
- 所有响应统一信封:

```json
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}
```

- 业务错误:`code != 0`,`data` 可能含 `details`
- 分页:`?page=1&page_size=20`,返回 `{ items, total, page, page_size }`
- 时间戳:ISO 8601,服务端统一 UTC
- ID:全部 ULID 字符串

### 6.2 端点总览

| Method | Path | 说明 | 异步 |
| --- | --- | --- | --- |
| POST | `/projects` | 创建项目并提交小说 | — |
| GET | `/projects` | 项目列表(对应前端左侧栏) | — |
| GET | `/projects/{id}` | 项目详情(聚合视图,对应工作台主数据) | — |
| PATCH | `/projects/{id}` | 修改基础信息 | — |
| DELETE | `/projects/{id}` | 删除项目 | — |
| POST | `/projects/{id}/parse` | 触发小说解析 + 自动分镜 | ✅ job |
| POST | `/projects/{id}/rollback` | 显式回退到更早 stage,清理下游绑定(见 §5.1) | — |
| GET | `/projects/{id}/storyboards` | 分镜列表 | — |
| PATCH | `/projects/{id}/storyboards/{shot_id}` | 编辑镜头文案 (仅 `stage ∈ {draft, storyboard_ready}` 可调) | — |
| POST | `/projects/{id}/storyboards` | 新增镜头 (同上编辑窗口) | — |
| DELETE | `/projects/{id}/storyboards/{shot_id}` | 删除镜头 (同上编辑窗口) | — |
| POST | `/projects/{id}/storyboards/reorder` | 批量调整顺序 (同上编辑窗口) | — |
| POST | `/projects/{id}/storyboards/confirm` | 确认分镜,推进到下一阶段 | — |
| GET | `/projects/{id}/characters` | 角色列表 | — |
| POST | `/projects/{id}/characters/generate` | 触发角色资产生成 | ✅ job |
| PATCH | `/projects/{id}/characters/{cid}` | 编辑角色描述/meta | — |
| POST | `/projects/{id}/characters/{cid}/regenerate` | 重新生成参考图 | ✅ job |
| POST | `/projects/{id}/characters/{cid}/lock` | 锁定为主角(或确认配角) | — |
| GET | `/projects/{id}/scenes` | 场景列表 | — |
| POST | `/projects/{id}/scenes/generate` | 根据镜头标签自动匹配模板并生成场景资产 | ✅ job |
| PATCH | `/projects/{id}/scenes/{sid}` | 编辑场景 | — |
| POST | `/projects/{id}/scenes/{sid}/regenerate` | 重新生成参考图 | ✅ job |
| POST | `/projects/{id}/scenes/{sid}/lock` | 锁定场景 | — |
| POST | `/projects/{id}/storyboards/{shot_id}/bind_scene` | 绑定镜头到场景 | — |
| POST | `/projects/{id}/shots/render` | 批量生成全部镜头 | ✅ job (总 + 子) |
| POST | `/projects/{id}/shots/{shot_id}/render` | 单镜头生成/重试 | ✅ job |
| POST | `/projects/{id}/shots/{shot_id}/renders/{render_id}/select` | 把历史版本切为当前 | — |
| POST | `/projects/{id}/shots/{shot_id}/lock` | 锁定为最终版 | — |
| GET | `/projects/{id}/shots/{shot_id}/renders` | 历史版本列表 | — |
| GET | `/projects/{id}/exports` | 导出任务列表 | — |
| POST | `/projects/{id}/exports` | 发起导出 | ✅ job |
| GET | `/exports/{export_id}` | 导出任务详情 | — |
| GET | `/jobs/{job_id}` | **前端轮询入口**:查任意异步任务状态 | — |

### 6.3 核心请求/响应示例

#### 6.3.1 创建项目

```http
POST /api/v1/projects
Content-Type: application/json

{
  "name": "宫墙风云 第 12 章",
  "story": "皇城夜雨,沈昭宁在冷宫废井旁……",
  "genre": "古风权谋",
  "ratio": "9:16",
  "setup_params": [
    "古风 / 写意漫感",
    "冷月青灰 + 朱砂点色",
    "短视频剧情号"
  ]
}

→ 200
{
  "code": 0,
  "data": {
    "id": "01HXXXXXXXXXXXXXXXXXXXXXXX",
    "stage": "draft",
    "created_at": "2026-04-20T10:15:00Z"
  }
}
```

#### 6.3.2 触发解析 + 分镜

```http
POST /api/v1/projects/{id}/parse

→ 200
{
  "code": 0,
  "data": {
    "job_id": "01HJOBXXXXXXXXXXXXXXXXXXXX"
  }
}
```

前端拿 `job_id` 轮询 `/jobs/{job_id}`。

#### 6.3.3 轮询任务

```http
GET /api/v1/jobs/{job_id}

→ 200
{
  "code": 0,
  "data": {
    "id": "01HJOB...",
    "kind": "gen_storyboard",
    "status": "running",
    "progress": 45,
    "total": 14,
    "done": 6,
    "result": null,
    "error_msg": null
  }
}
```

完成后 `status=succeeded`,`result` 内填业务结果摘要(如新生成的镜头 id 列表),前端根据 `kind` 决定下一步行为。

#### 6.3.4 显式回退

```http
POST /api/v1/projects/{id}/rollback
Content-Type: application/json

{
  "to_stage": "storyboard_ready"
}

→ 200
{
  "code": 0,
  "data": {
    "from_stage": "rendering",
    "to_stage": "storyboard_ready",
    "invalidated": {
      "shots_reset": 14,
      "characters_unlocked": 3,
      "scenes_unlocked": 3
    }
  }
}

→ 40301 (不能回退到更晚阶段或跳级)
```

#### 6.3.5 项目聚合详情(前端工作台主数据源)

```http
GET /api/v1/projects/{id}

→ 返回与前端 types/index.ts 中 ProjectData 对齐的聚合数据,包含 storyboards/characters/scenes/generationQueue/exportTasks
```

**契约约束**:该接口返回的 JSON 字段命名与前端 `ProjectData` 类型保持一对一;如需改名,前后端同步改。

#### 6.3.6 批量渲染镜头

```http
POST /api/v1/projects/{id}/shots/render
Content-Type: application/json

{
  "shot_ids": null,          // null 表示全部未完成镜头
  "force_regenerate": false
}

→ 200
{
  "code": 0,
  "data": {
    "job_id": "01HJOBBATCH...",
    "sub_job_ids": ["01H...", "01H...", ...]   // 每个子镜头一个 job
  }
}
```

#### 6.3.7 发起导出

```http
POST /api/v1/projects/{id}/exports
Content-Type: application/json

{
  "name": "宫墙风云 第 12 章 - 第一版",
  "config": {
    "resolution": "1080x1920",
    "ratio": "9:16",
    "per_shot_duration": [2.5, 4.0],
    "transition": "dissolve+cut_black"
  }
}

→ 200 / 409 (若有未完成镜头)
{
  "code": 0,
  "data": { "export_id": "01H...", "job_id": "01H..." }
}

409 示例:
{
  "code": 40901,
  "message": "有未完成镜头,无法导出",
  "data": { "pending_shot_ids": ["01H...", "01H..."] }
}
```

### 6.4 错误码

| code | 含义 |
| --- | --- |
| 0 | 成功 |
| 40001 | 参数校验失败(返回 details 数组) |
| 40301 | 当前 stage 不允许该操作 |
| 40401 | 资源不存在 |
| 40901 | 业务冲突(如导出时有未完成镜头) |
| 42901 | AI 限流,请稍后重试 |
| 50001 | 内部错误 |
| 50301 | 上游 AI 服务不可用 |

---

## 7. 异步任务设计

### 7.1 队列划分

- `ai` queue:LLM / 图像生成,IO bound,worker 并发数 = `AI_WORKER_CONCURRENCY`(默认 8),带全局令牌桶限流(保护火山额度)
- `video` queue:FFmpeg 合成,CPU bound,worker 并发数 = `VIDEO_WORKER_CONCURRENCY`(默认 2)

### 7.2 任务清单

| task | queue | 幂等键 | 重试策略 |
| --- | --- | --- | --- |
| `parse_novel` | ai | `project_id` | 最多 3 次,指数退避 4/16/64s |
| `gen_storyboard` | ai | `project_id` | 3 次,60s 间隔 |
| `gen_character_asset` | ai | `character_id` | 3 次 |
| `gen_scene_asset` | ai | `scene_id` | 3 次 |
| `render_shot` | ai | `shot_id + version_no` | 按错误类别分级,见下 |
| `render_batch` | ai | `sha1(project_id + sorted(shot_ids) + force_regenerate + ts_minute)` | 不重试,只是分发器;幂等窗口按分钟级粒度避免重复误判 |
| `export_video` | video | `export_task_id` | 2 次 |

**`render_shot` 按错误类别的重试策略**:

| 错误类别 | 判别 | 最大尝试数 | 退避 |
| --- | --- | --- | --- |
| 限流 / 临时网络 / 5xx | HTTP 429 / 502 / 503 / 504、超时 | 3 | 指数 4/16/64s |
| 内容违规 / 参数错 | 4xx 非 429 | 1(不自动重试) | — |
| provider 已接单但 worker crash | 重启后扫描 `status=running` 且 `provider_task_id` 非空 | 不算重试,转走回查流程(见 §7.4) | — |

> `render_batch` 的幂等窗口:以分钟截断 ts(`int(time()/60)`)参与 hash,确保 60s 内完全相同的入参不会重复分发,但超过 1 分钟的"再次批渲"视为新请求,匹配用户行为。

### 7.3 进度上报

- worker 每完成一个关键步骤调用 `pipeline.transitions.update_job_progress(job_id, done, total)`,只更新 `jobs` 行
- 批量任务(`render_batch`):主 job 的 `total=镜头数`,每个子 task 完成后原子 `done += 1`
- 失败策略:子 task 失败记录到 `shot_renders.error_msg`,主 job 继续跑完其他镜头;最终主 job 状态按"是否有失败子 task"决定 `succeeded`/`failed`(partial success 也标 failed,但 result 里列清失败子集)

### 7.4 断点续跑

- Worker 启动时扫描 `status='running'` 且 `updated_at` 超 10 分钟的 `jobs` 行,重新入队(幂等键保证不会重复副作用)
- `render_shot` 在开始时写入 `shot_renders` 行(status=running),worker crash 后可以基于 `provider_task_id` 向火山查询并回收结果,而不是直接重跑

---

## 8. 存储设计

### 8.1 目录规则

```
/data/assets/
  └── {project_id}/
        ├── character/{yyyymmdd}/{ulid}.png
        ├── scene/{yyyymmdd}/{ulid}.png
        ├── shot/{shot_id}/v{version_no}.png
        └── export/{export_id}.mp4
        └── export/{export_id}_cover.jpg
```

### 8.2 Nginx 映射

```nginx
location /static/ {
  alias /data/assets/;
  add_header Cache-Control "public, max-age=2592000";
  # 仅允许内网或可配置 referer
}
```

数据库里存 **相对路径**(如 `gongqiang/shot/01H.../v1.png`),应用层拼 `STATIC_BASE_URL`(可配置,如 `https://comic.internal/static/`)。

### 8.3 清理策略

- 软删除项目时,异步任务在 24h 后清理磁盘
- 历史 render 版本不自动清理(保留回退能力);提供 `POST /admin/projects/{id}/vacuum` 手工回收非当前版本图片

---

## 9. 配置与环境变量

```
# 数据库
DATABASE_URL=mysql+asyncmy://root:***@172.16.7.108:3308/comic_drama

# Redis
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2

# 存储
STORAGE_ROOT=/data/assets
STATIC_BASE_URL=http://comic.internal/static/

# 火山
VOLCANO_ACCESS_KEY=***
VOLCANO_SECRET_KEY=***
VOLCANO_LLM_MODEL=doubao-pro-32k
VOLCANO_IMG_MODEL=seedream-...
VOLCANO_BASE_URL=https://...

# worker
AI_WORKER_CONCURRENCY=8
VIDEO_WORKER_CONCURRENCY=2
AI_RATE_LIMIT_PER_MIN=120

# 服务
APP_ENV=dev|prod
LOG_LEVEL=INFO
```

统一通过 `app/config.py`(Pydantic Settings)加载,测试环境可 override。

---

## 10. 错误处理原则

- **上游 AI 失败**:捕获 `VolcanoError`,分类为"限流 / 超时 / 内容违规 / 其他",落到 `shot_renders.error_code`,前端可针对"违规"提示用户改文案
- **DB 约束冲突**:`UNIQUE` 违例转 409
- **stage 不匹配**:`pipeline.transitions` 抛 `InvalidTransition`,统一 403/40301
- **全局异常处理器**:`app/main.py` 注册,所有未捕获异常 500,并把 `request_id`(UUID)写日志
- 不做重试/兜底的场景:参数校验、stage 错误、资源不存在——立即返回不重试

---

## 11. 测试策略

- **单元测试**(`tests/unit/`):domain/services 与 pipeline/transitions,不连 DB,mock 掉 repo
- **集成测试**(`tests/integration/`):FastAPI TestClient + 真实 MySQL(CI 用 docker 拉起)+ fake VolcanoClient(返回固定占位图 / 假分镜 JSON)+ eager Celery(`CELERY_TASK_ALWAYS_EAGER=True`)
- **端到端冒烟**:脚本 `scripts/e2e_smoke.py` 模拟一次完整链路(创建项目 → 解析 → 角色锁定 → 场景锁定 → 渲染 → 导出),每次 PR 合并前跑一次
- **覆盖目标**:pipeline/transitions 100%,domain/services ≥ 80%,API 层 ≥ 60%

---

## 12. 部署

### 12.1 docker-compose 服务

```yaml
services:
  mysql:         # 开发用,生产复用现有实例
  redis:
  api:           # uvicorn app.main:app --workers 2
  celery-ai:     # celery -A app.tasks.celery_app worker -Q ai -c 8
  celery-video:  # celery -A app.tasks.celery_app worker -Q video -c 2
  nginx:         # 静态文件 + API 反代
```

### 12.2 启动顺序

1. `alembic upgrade head`
2. 启动 `mysql` / `redis`
3. 启动 `api` + `celery-ai` + `celery-video`
4. 启动 `nginx`

### 12.3 健康检查

- `GET /healthz`:DB ping + Redis ping + 存储目录可写
- `GET /readyz`:上述 + 检查是否能读到火山 endpoint(HEAD 请求)

---

## 13. 与前端 demo 的契约

### 13.1 字段映射(完整对照 `src/types/index.ts`)

后端 `GET /projects/{id}` 响应的 `data` 与前端 `ProjectData` 字段一对一。所有展示串由后端拼好,前端直接渲染不转换。

**顶层 `ProjectData`**:

| 前端字段 | 前端类型 | 后端来源 | 说明 |
| --- | --- | --- | --- |
| `id` | string | `projects.id` | |
| `name` | string | `projects.name` | |
| `stage` | `ProjectStage` | `projects.stage` → 见 §13.2 | 7 值中文枚举,与内部 ENUM 一一对应,前端展示与判定同口径 |
| `stage_raw` | `ProjectStageRaw` | `projects.stage` 原值 | 英文 ENUM(7 值);前端阶段门 `useStageGate` 基于此字段做比较,避免中文字符串匹配 |
| `genre` | string | `projects.genre` | |
| `ratio` | string | `projects.ratio` + `" 竖屏"` | 后端拼 `"9:16 竖屏"` |
| `suggestedShots` | string | `"建议镜头数 " + projects.suggested_shots` | |
| `story` | string | `projects.story` | |
| `summary` | string | `projects.summary` | |
| `parsedStats` | string[] | `projects.parsed_stats` | JSON 数组直出 |
| `setupParams` | string[] | `projects.setup_params` | 同上 |
| `projectOverview` | string | `projects.overview` | |
| `storyboards` | `StoryboardShot[]` | 见下表 | |
| `characters` | `CharacterAsset[]` | 见下表 | |
| `scenes` | `SceneAsset[]` | 见下表 | |
| `generationProgress` | string | `` `${succeeded} / ${total} 已完成` `` | 服务端计算 |
| `generationNotes` | `{input,suggestion}` | `{ input: 最近一次 render 的 prompt_snapshot 摘要, suggestion: AI 或规则生成的下一轮优化建议 }` | MVP `suggestion` 可先写固定规则,后期走 LLM |
| `generationQueue` | `RenderQueueItem[]` | 取每个 shot 的 `current_render` | 见下表 |
| `exportConfig` | string[] | `export_tasks` 最新任务的 config 展平 | `["比例:9:16","分辨率:1080 x 1920",...]` |
| `exportDuration` | string | `"预计成片时长:" + Σ(duration_sec) + " 秒"` | |
| `exportTasks` | `ExportTask[]` | `export_tasks where project` | 见下表 |

**`StoryboardShot`**:

| 前端字段 | 后端来源 |
| --- | --- |
| `id` | `storyboards.id` |
| `index` | `storyboards.idx` |
| `title` | `storyboards.title` |
| `description` | `storyboards.description` |
| `detail` | `storyboards.detail` |
| `duration` | `` `${duration_sec} 秒` `` |
| `tags` | `storyboards.tags` (JSON 数组直出) |

**`CharacterAsset`**:

| 前端字段 | 后端来源 |
| --- | --- |
| `id` | `characters.id` |
| `name` | `characters.name` |
| `role` | 由 `role_type` 映射:`protagonist→"主角"` / `supporting→"关键配角"` / `atmosphere→"氛围配角"`(若 role_type 不足表达,DB 可扩 `role_label` VARCHAR 覆盖) |
| `summary` | `characters.summary` |
| `description` | `characters.description` |
| `meta` | `characters.meta` |

**`SceneAsset`**:

| 前端字段 | 后端来源 |
| --- | --- |
| `id` | `scenes.id` |
| `name` | `scenes.name` |
| `summary` | `scenes.summary` |
| `usage` | `` `场景复用 ${被多少 shot 绑定} 镜头` `` | 由 scene_id 反查 count 计算 |
| `description` | `scenes.description` |
| `meta` | `scenes.meta` |
| `theme` | `scenes.theme` |

**`RenderQueueItem`**:

| 前端字段 | 后端来源 |
| --- | --- |
| `id` | `storyboards.id`(每个 shot 一条) |
| `title` | `"镜头 " + zero_padded(idx)` |
| `summary` | `storyboards.title` |
| `status` | 由 `storyboards.status` 映射:`succeeded/locked→success` / `generating→processing` / `failed/pending→warning` |

**`ExportTask`**:

| 前端字段 | 后端来源 |
| --- | --- |
| `id` | `export_tasks.id` |
| `name` | `export_tasks.name` |
| `summary` | 服务端按 status 生成一句人读摘要,如 `"正在合成中,已完成封面、片头与 X 个镜头拼接"` |
| `status` | `export_tasks.status` 映射:`succeeded→success` / `running→processing` / `queued/failed→warning` |
| `progressLabel` | 若 `status=succeeded` 返回 `"完成"`;若 `running` 返回 `"{progress}%"`;若 `queued/failed` 返回 `"待完成"` |

### 13.2 stage 中文映射(7 值,与内部 ENUM 一对一)

前端 `ProjectStage` 扩为 7 值,和内部 ENUM 完全对齐,避免"展示口径丢失阶段信息"。原 3 值折叠方案作废。

| 后端 stage (stage_raw) | 前端 stage (展示值) |
| --- | --- |
| `draft` | `草稿中` |
| `storyboard_ready` | `分镜已生成` |
| `characters_locked` | `角色已锁定` |
| `scenes_locked` | `场景已匹配` |
| `rendering` | `镜头生成中` |
| `ready_for_export` | `待导出` |
| `exported` | `已导出` |

> **字段用途约定**:
> - `stage`:仅用于 UI 展示(项目列表卡片上的 tag、工作台顶部状态 pill)
> - `stage_raw`:前端做阶段门逻辑、条件渲染、路由守卫时使用
> - 管理接口(`/jobs`、`/rollback`、`/storyboards/confirm` 等)请求/响应一律使用英文 ENUM
> - `projects.stage` 在数据库内始终为英文 ENUM
>
> **为什么同时返回两个**:前端 TS 对展示字符串做联合类型能锁死文案拼写;但用中文做条件判断会让 diff 噪声大、重构风险高。前端约定:`v-if="stage_raw === 'rendering'"` 用 raw,`<span>{{ stage }}</span>` 用展示值。

---

## 14. 风险与开放问题

- **火山图像模型角色一致性**:真实接入后若一致性不够,可能需要引入 LoRA 或参考图分镜级增强 → 在 `shot_renders.prompt_snapshot` 已预留完整上下文,后续不改表
- **视频合成耗时**:FFmpeg 串行合成 20 个镜头估算 30~90 秒,`video` worker 独立避免阻塞 AI 任务
- **MVP 不做软删除**:`DELETE /projects/{id}` 是硬删,级联清理;如果后期要撤销,需加 `deleted_at` 列并改所有查询
- **配额/并发保护**:`AI_RATE_LIMIT_PER_MIN` 是粗粒度,若火山按模型分别计费,需要后续在 `VolcanoClient` 里按 model 区分令牌桶

---

## 15. 里程碑拆解(建议)

| M | 交付 |
| --- | --- |
| M1 | 基础骨架:FastAPI + SQLAlchemy + Alembic + Celery 跑通 hello world;项目 CRUD + rollback 端点 + stage 状态机骨架(mock 阶段跃迁) |
| M2 | Pipeline + mock VolcanoClient:小说解析 + 分镜生成(假数据)全流程;前端能走通工作台 UI,前后端字段一对一联调通过 |
| M3a | 接真实火山(文本+图像):角色资产生成、场景资产生成与锁定 |
| M3b | 单镜头渲染:`render_shot` 全链路打通、`shot_renders` 版本表、历史版本切换接口 |
| M3c | 批量渲染:`render_batch` 聚合 job、按错误类别重试策略、worker crash 后回查恢复(§7.4) |
| M4 | 导出链路:FFmpeg 合成 + `export_shot_snapshots` 快照 + 下载 + 导出前完整性校验 |
| M5 | 运维收尾:断点续跑全场景覆盖、错误码矩阵、集成测试 ≥80%、docker-compose 一键部署、健康检查 |

---

## 16. 一句话总结

本设计把产品文档定义的"小说→分镜→角色→场景→渲染→导出"流水线翻译成 **一条由 `pipeline/` 集中守护、由 Celery 双队列驱动、由 MySQL + 本地文件系统落地** 的 MVP 后端实现,接口与数据模型与前端 demo 字段一一对齐,可在后续不改表结构的前提下替换 AI 供应商、加鉴权、加团队、扩存储。
