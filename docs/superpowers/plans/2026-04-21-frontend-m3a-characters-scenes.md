# Frontend M3a: 角色/场景资产写操作 + 主角锁定 + bind_scene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M2 已交付的 "create → parse → storyboards CRUD → confirm" 闭环之上,对接后端 M3a 新增的 11 个业务端点(角色 5 条 + 场景 5 条 + storyboards.bind_scene 1 条),把 `CharacterAssetsPanel` / `SceneAssetsPanel` 从纯只读升级为完整可交互,打通"生成角色 → 编辑 → 重生成 → 锁定主角 → 生成场景 → 绑定镜头 → 锁定场景"的 M3a 工作流,并严格按 `useStageGate` 对齐后端 §5.1 编辑窗口。

**Architecture:** 延续 M2 策略:所有写操作成功后 `await workbench.reload()`,由后端聚合 `GET /projects/{id}` 回写统一快照,前端不做乐观合并。generate 任务走"主 job + 子 jobs"聚合结构 —— 前端只轮询**主 job**(`ack.job_id`),进度从主 job 的 `done/total` 派生,终态 `succeeded` → `reload()` 获取落库后的角色/场景与 `reference_image_url`;子 `sub_job_ids` 仅作为日后"单项失败定位"的调试入口,本期不强制展开。`regenerate` 走单 job 轮询(复用 useJobPolling 成熟模式),同一 panel 同时只允许一个同类 regen job。`lockCharacter(as_protagonist=true)` 后端内部触发 `ensure_character_asset_registered` 同步调用人像库(最多 120s),前端对该请求放宽 timeout 到 150s,期间 lock 按钮置 busy 并展示 persist info toast;人像库状态通过 reload 后的 `meta: string[]` 里的 "人像库:Active/Pending/…" 尾条读出。

**Tech Stack:** 沿用 M1/M2(Vue 3.5 `<script setup>` / TS 5.7 strict / Vite 6 / Pinia 2 / Axios 1.x / Vitest 2 + @vue/test-utils);不新增运行时依赖。

**References:**
- 前端 spec:`docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §5.2 / §7.3.3 / §7.3.4 / §8 / §9 / §15 M3a
- 后端 M3a plan(端点契约来源):`docs/superpowers/plans/2026-04-21-backend-m3a-real-volcano-and-assets.md` Task 7(characters)/ Task 8(scenes)/ Task 9(pipeline)/ Task 11(bind_scene)/ Task 12(聚合)/ Task 15(42201 错误码)
- 后端 spec:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §5.1(编辑窗口)/ §6.2(端点)/ §6.4(错误码,含新登记 42201)/ §13.1(聚合契约)
- Frontend M1/M2 plans:已交付的 API 客户端 / store / useJobPolling / useStageGate 模式
- 视觉参考源:`product/workbench-demo/`(M3a 仍不做视觉再设计)

---

## M2 Review 遗留

**状态**: 无遗留问题。M2 已 `npm run test` 全绿 + `npm run typecheck` 通过 + `smoke_m2.sh` 绿。M3a 可直接在 M2 基础上开始实施。

---

## M3a 范围与非范围

### 本里程碑交付

- `types/api.ts` 新增 `CharacterOut` / `SceneOut` / `CharacterUpdate` / `SceneUpdate` / `CharacterGenerateRequest` / `SceneGenerateRequest` / `CharacterLockRequest` / `CharacterLockResponse` / `SceneLockRequest` / `SceneLockResponse` / `GenerateJobAck` / `BindSceneRequest` / `BindSceneResponse`
- `types/index.ts` 扩展 `CharacterAsset`(新增 `reference_image_url?: string | null` / `is_protagonist: boolean` / `locked: boolean`) + `SceneAsset`(新增 `reference_image_url?: string | null` / `locked: boolean` / `theme: SceneThemeRaw`)
- `api/characters.ts`(新建)与后端 5 条 characters 端点 1:1
- `api/scenes.ts`(新建)与后端 5 条 scenes 端点 1:1 + `api/storyboards.ts` 新增 `bindScene`
- `store/workbench.ts` 新增字段 `activeGenerateCharactersJobId` / `activeGenerateScenesJobId` / `regenJobs` + `regenJobIdFor(kind,id)`(单项 regen 的单 job 追踪,key 形如 `"character:<id>"`);新增写动作 `generateCharacters` / `patchCharacter` / `regenerateCharacter` / `lockCharacter` / `generateScenes` / `patchScene` / `regenerateScene` / `lockScene` / `bindShotScene` + 对应 `mark*Succeeded` / `mark*Failed`
- `CharacterAssetsPanel.vue` 全面重写:空态大按钮 → 触发 `POST /characters/generate` → 主 job 进度条 → 终态 reload;列表显示「主角·已锁定」徽章;详情区 `reference_image_url` 实图替换占位 silhouette;按钮 `编辑描述` / `重新生成参考图` / `设为主角 · 锁定` / `仅锁定`;`meta: string[]` 展示后端拼好的 tag(含 `人像库:<status>`)
- `SceneAssetsPanel.vue` 全面重写:空态大按钮 → `POST /scenes/generate` → 轮询主 job → reload;详情区加入 `重新生成参考图` / `锁定场景` / `绑定当前镜头` 按钮;依据 `scene.reference_image_url` 优先实图,缺失回落到 demo 的 `theme-palace/academy/harbor` 装饰层
- 新组件 `components/character/CharacterEditorModal.vue`:编辑 `name/summary/description/role_type`(role_type 下拉 protagonist/supporting/atmosphere)
- 新组件 `components/scene/SceneEditorModal.vue`:编辑 `name/theme/summary/description`
- 阶段门严格执行:`canGenerateCharacters` = `stage_raw === "storyboard_ready"`;`canGenerateScenes` = `stage_raw === "characters_locked"`;编辑 character = `stage_raw === "storyboard_ready"`;编辑 scene = `stage_raw === "characters_locked"`;`bind_scene` = `stage_raw === "characters_locked"`;所有拦截路径 toast + `StageRollbackModal`
- 42201 "AI 内容违规" 错误码映射(`utils/error.ts` 新增常量 + 文案)
- Vitest 覆盖:`api/characters` / `api/scenes` 请求拼装 + `workbench` 新动作(generateCharacters / lockCharacter / regenerateCharacter / bindShotScene 等)
- `scripts/smoke_m3a.sh` 全链路冒烟:建项目 → parse → confirm → generate characters → lock protagonist → generate scenes → bind & lock scenes → 断言 `stage_raw=scenes_locked`
- `frontend/README.md` 新增 "M3a 范围"

### 非范围(留给后续)

- 镜头渲染、render 版本历史、批量重渲(M3b/c)
- 导出、下载、缺失列表跳转(M4)
- "手动新增角色 / 新增场景"(后端无对应 POST 端点;demo 里的 "新增角色资产" / "新增场景资产" 按钮 **M3a 继续保持 `disabled` 占位**,与 spec §7.3.3/§7.3.4 一致)
- 分镜拖拽绑定场景(M3a 只用"当前选中 shot → 绑到当前选中 scene"按钮;拖拽 M3b+)
- 子 job 级失败列表展开(子 job 失败后 toast + `meta` 里回读即可;完整子 job timeline 留 M3c)
- 主角人像库进度条 UI(本期通过 `meta` 里 "人像库:Active/Pending" 文本体现状态,不做专用进度 UI)
- 阶段门拓扑变动(useStageGate 本已覆盖 M3a 全部布尔;不新增 flag)

---

## 前置依赖:前后端聚合与 bind_scene 契约对齐(⚠️ 必须先做)

**当前事实**: 后端 M3a 已经为聚合 `characters[]` 输出 `role_type` / `is_protagonist` / `locked` / `reference_image_url`,也已经为聚合 `scenes[]` 输出 `locked` / `template_id` / `reference_image_url`。这些字段不再是阻断项,Task 0 只需要用 curl/测试核对,不要重复实现。

**仍需修正的阻断项**:

- `aggregate_service.py` 的 `characters[].meta` / `scenes[].meta` 仍是空数组 TODO,必须把 `meta` 与 `video_style_ref.asset_status` 摘要成前端展示 tag,例如 `"人像库:Active"` / `"人像库:Pending"`。
- `bind_scene` 当前仍是 query 参数 `scene_id` + 响应 `{id, scene_id}`,需要统一为 JSON body `{scene_id}` + 响应 `{shot_id, scene_id, scene_name}`。
- `SceneService.bind_scene_to_shot` 必须在 service 层校验阶段,错误阶段抛 `InvalidTransition` → `40301`;仅靠前端 `canBindScene` 不够。
- `generate_characters` / `generate_scenes` 的阶段错误必须统一走 `InvalidTransition` / `assert_asset_editable`,不要继续直接抛 `HTTPException(400)`。
- 顺手修掉两个已存在的角色接口 bug:`GET /characters` 中 `role_map` 未定义,以及 `PATCH /characters/{cid}` 返回 `role=char.role_type` 英文枚举。
- 聚合 `storyboards[]` 补齐 `current_render_id` / `created_at` / `updated_at`,与前端 `StoryboardDetail` 类型一致。

**落实**: 在 Task 0 里以 PR 方式改 backend `aggregate_service.py` + `storyboards.bind_scene` + `SceneService.bind_scene_to_shot` + `characters/scenes generate` 阶段错误 + 角色接口兼容 bug + 同步 backend spec/plan。**未合入前,本 plan 所有后续任务都应 block**。

---

## 文件结构(M3a 交付的所有文件)

**新建**:

```
frontend/
├── scripts/
│   └── smoke_m3a.sh                              # M3a 冒烟
└── src/
    ├── api/
    │   ├── characters.ts                         # 5 条 characters 端点
    │   └── scenes.ts                             # 5 条 scenes 端点
    └── components/
        ├── character/
        │   └── CharacterEditorModal.vue          # 角色编辑弹窗
        └── scene/
            └── SceneEditorModal.vue              # 场景编辑弹窗

tests/unit/
├── characters.api.spec.ts                        # mock client 测请求拼装
├── scenes.api.spec.ts                            # 同上
└── workbench.m3a.store.spec.ts                   # generate/lock/regen/bind 动作
```

**修改**:

```
frontend/
├── README.md                                     # 新增 "M3a 范围" 一节
└── src/
    ├── api/
    │   └── storyboards.ts                        # 新增 bindScene(projectId, shotId, { scene_id })
    ├── types/
    │   ├── api.ts                                # 新增 Character*/Scene*/BindScene* 类型
    │   └── index.ts                              # 扩展 CharacterAsset / SceneAsset
    ├── utils/
    │   └── error.ts                              # 新增 CONTENT_FILTER=42201 + 文案
    ├── store/
    │   └── workbench.ts                          # 新动作 + 新 job 追踪字段
    ├── composables/
    │   └── useStageGate.ts                       # 新增 canEditCharacters / canEditScenes / canBindScene / canLockCharacter / canLockScene
    └── components/
        ├── character/
        │   └── CharacterAssetsPanel.vue          # 全面可交互
        └── scene/
            └── SceneAssetsPanel.vue              # 全面可交互
```

---

## 实施前提

- 已在 `feat/frontend-m3a` 分支,M2 已 merge 到当前分支
- 前置依赖(见上一节)已合入:后端 aggregate 输出包含 `is_protagonist` / `locked` / `meta` 人像库状态 / storyboard 时间字段,且 `bind_scene` 使用 JSON body `{scene_id}` 并返回 `shot_id/scene_id/scene_name`;可用 `curl -s http://127.0.0.1:8000/api/v1/projects/<id> | jq '.data.characters[0] | keys'` 验证聚合字段
- 后端 M3a 已交付并跑通 `./backend/scripts/smoke_m3a.sh`(`AI_PROVIDER_MODE=mock` + `CELERY_TASK_ALWAYS_EAGER=true` 下一次 HTTP 请求内走完 generate 链);本前端 plan **不依赖真实火山**,mock 模式足够调通所有路径
- `VITE_API_BASE_URL=/api/v1`,vite 代理已通过 M1 配好,M3a 不改 `vite.config.ts`
- 本地可执行 `cd frontend && npm install && npm test`

---

## Task 0: 前置契约对齐 — 后端 M3a 契约补洞

**Files:**
- Modify(backend):`backend/app/domain/services/aggregate_service.py`
- Modify(backend):`backend/app/api/storyboards.py`
- Modify(backend):`backend/app/domain/services/scene_service.py`
- Modify(backend):`backend/app/domain/schemas/storyboard.py`
- Modify(backend):`backend/app/api/characters.py`
- Modify(backend):`backend/app/api/scenes.py`
- Modify(backend spec):`docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §13.1 字段映射表
- Modify(backend plan):`docs/superpowers/plans/2026-04-21-backend-m3a-real-volcano-and-assets.md` Task 11/12 代码块

> 这一任务是前后端 joint PR;前端 plan 后续所有 task 都 block on 此任务 merged。若已由后端同步开了独立 PR,本任务只做核对 + spec 同步即可。

- [ ] **Step 1: 核对 aggregate 已有字段 — `characters[]` / `scenes[]` 锁定字段**

当前 M3a 后端已落库并聚合输出这些字段,执行者只需用测试/curl 断言,不要重复改:

- `characters[]`: `role_type`, `is_protagonist`, `locked`, `reference_image_url`
- `scenes[]`: `locked`, `template_id`, `reference_image_url`

```bash
curl -s http://127.0.0.1:8000/api/v1/projects/<id> \
  | jq '.data.characters[0] | {role_type,is_protagonist,locked,reference_image_url}'

curl -s http://127.0.0.1:8000/api/v1/projects/<id> \
  | jq '.data.scenes[0] | {locked,template_id,reference_image_url}'
```

- [ ] **Step 2: 改 aggregate — meta tag 与 storyboards 契约补齐**

```python
def _meta_to_tags(meta: dict | None, video_style_ref: dict | None) -> list[str]:
    tags: list[str] = []
    if isinstance(meta, dict):
        tags.extend(str(v) for v in meta.get("tags", []) if v)
    if isinstance(video_style_ref, dict) and video_style_ref.get("asset_status"):
        tags.append(f"人像库:{video_style_ref['asset_status']}")
    return tags

# storyboards[] 字典补齐:
"current_render_id": s.current_render_id,
"created_at": s.created_at,
"updated_at": s.updated_at,

# characters[] / scenes[] 使用:
"meta": _meta_to_tags(c.meta, c.video_style_ref),
"meta": _meta_to_tags(s.meta, s.video_style_ref),
```

- [ ] **Step 3: 改 bind_scene — 请求体使用 JSON body,响应返回 `shot_id` / `scene_id` / `scene_name`**

```python
# backend/app/domain/schemas/storyboard.py
class BindSceneRequest(BaseModel):
    scene_id: str = Field(..., min_length=1)

class BindSceneResponse(BaseModel):
    shot_id: str
    scene_id: str
    scene_name: str
```

```python
# backend/app/api/storyboards.py
@router.post("/{shot_id}/bind_scene")
async def bind_scene(
    project_id: str,
    shot_id: str,
    payload: BindSceneRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        shot, scene = await SceneService.bind_scene_to_shot(
            db, project_id, shot_id, payload.scene_id
        )
        await db.commit()
        return ok({
            "shot_id": shot.id,
            "scene_id": scene.id,
            "scene_name": scene.name,
        })
    except ValueError as e:
        raise ApiError(40001, str(e))
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)
```

```python
# backend/app/domain/services/scene_service.py
@staticmethod
async def bind_scene_to_shot(
    session: AsyncSession,
    project_id: str,
    shot_id: str,
    scene_id: str,
) -> tuple[StoryboardShot, Scene]:
    project = await session.get(Project, project_id)
    if not project:
        raise ValueError("项目不存在")
    assert_asset_editable(project, "scene")

    # 保留现有 shot / scene 归属校验
    shot.scene_id = scene_id
    return shot, scene
```

> service 层是必须项:错误阶段要抛 `InvalidTransition` → `40301`,与前端 `canBindScene` 保持一致,避免脚本/CI 越权 bind。

- [ ] **Step 4: 补 lock / generate 阶段校验,统一阶段错误码为 `40301`**

```python
# backend/app/domain/services/character_service.py
async def lock(...):
    assert_asset_editable(project, "character")
    # 保留现有 as_protagonist / ensure_character_asset_registered / advance 逻辑

# backend/app/domain/services/scene_service.py
async def lock(...):
    assert_asset_editable(project, "scene")
    # 保留现有 scene.locked = True + advance_to_scenes_locked 逻辑

# backend/app/api/characters.py
project = (await db.execute(stmt)).scalar_one_or_none()
if not project:
    raise ApiError(40401, "项目不存在", http_status=404)
assert_asset_editable(project, "character")

# backend/app/api/scenes.py
project = (await db.execute(stmt)).scalar_one_or_none()
if not project:
    raise ApiError(40401, "项目不存在", http_status=404)
assert_asset_editable(project, "scene")
```

`assert_asset_editable` 抛出的 `InvalidTransition` 会被全局 handler 包成 HTTP 403 + `40301`;若在 router 里手动 catch,必须传 `http_status=403`。不要再使用 `HTTPException(status_code=400, detail="项目阶段不支持生成...")`。

- [ ] **Step 5: 修角色接口两个既有 bug**

```python
ROLE_CN = {"protagonist": "主角", "supporting": "配角", "atmosphere": "氛围"}

# GET /characters 与 PATCH /characters/{cid} 都使用:
role=ROLE_CN.get(char.role_type, char.role_type)
```

- [ ] **Step 6: 同步 backend spec §6.2/§13.1**

`CharacterAsset` / `SceneAsset` 表的"前端字段"列确认 `is_protagonist: bool` / `locked: bool`(character)、`locked: bool`(scene);`meta` 明确包含人像库状态 tag;`StoryboardDetail` 明确包含 `current_render_id` / `created_at` / `updated_at`;`POST /storyboards/{shot_id}/bind_scene` 明确请求体 `{ scene_id }`,响应 `{ shot_id, scene_id, scene_name }`。

- [ ] **Step 7: 在后端 integration 测 `test_projects_api.py` / `test_bind_scene.py`(或等价处)断言上述契约**

```python
@pytest.mark.asyncio
async def test_aggregate_includes_lock_flags(client, project_with_chars_and_scenes):
    pid, protagonist_id, locked_scene_id = project_with_chars_and_scenes
    resp = await client.get(f"/api/v1/projects/{pid}")
    data = resp.json()["data"]
    prot = next(c for c in data["characters"] if c["id"] == protagonist_id)
    assert prot["is_protagonist"] is True
    assert prot["locked"] is True
    assert any(t.startswith("人像库:") for t in prot["meta"])
    locked_scene = next(s for s in data["scenes"] if s["id"] == locked_scene_id)
    assert locked_scene["locked"] is True
    shot = data["storyboards"][0]
    assert {"current_render_id", "created_at", "updated_at"} <= set(shot)

@pytest.mark.asyncio
async def test_bind_scene_uses_json_body_and_returns_scene_name(client, project_with_shot_and_scene):
    pid, shot_id, scene_id, scene_name = project_with_shot_and_scene
    resp = await client.post(
        f"/api/v1/projects/{pid}/storyboards/{shot_id}/bind_scene",
        json={"scene_id": scene_id},
    )
    data = resp.json()["data"]
    assert data == {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "scene_name": scene_name,
    }

@pytest.mark.asyncio
async def test_bind_scene_rejects_wrong_stage_with_40301(client, project_with_draft_shot_and_scene):
    pid, shot_id, scene_id = project_with_draft_shot_and_scene
    resp = await client.post(
        f"/api/v1/projects/{pid}/storyboards/{shot_id}/bind_scene",
        json={"scene_id": scene_id},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40301
```

- [ ] **Step 8: Commit(后端仓)**

```bash
git add backend/app/domain/services/aggregate_service.py \
        backend/app/api/storyboards.py \
        backend/app/domain/services/character_service.py \
        backend/app/domain/services/scene_service.py \
        backend/app/domain/schemas/storyboard.py \
        backend/app/api/characters.py \
        backend/app/api/scenes.py \
        backend/tests/integration/test_projects_api.py \
        backend/tests/integration/test_bind_scene.py \
        docs/superpowers/specs/2026-04-20-backend-mvp-design.md \
        docs/superpowers/plans/2026-04-21-backend-m3a-real-volcano-and-assets.md
git commit -m "feat(backend): 对齐前端 M3a 契约缺口"
```

Expected: 后端 `cd backend && ./.venv/bin/pytest -v` 全绿;`curl /projects/<id> | jq '.data.characters[0]'` 可见 `is_protagonist` / `locked` / `meta:["人像库:<status>"]`;`curl -X POST /storyboards/<shot_id>/bind_scene -d '{"scene_id":"..."}'` 返回 `shot_id` / `scene_id` / `scene_name`,错误阶段返回 HTTP 403 + envelope `40301`。

---

## Task 1: 前端类型扩充 — api.ts + index.ts

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: `types/api.ts` 末尾追加 M3a 类型(与后端 `CharacterOut` / `SceneOut` 等 1:1)**

```ts
// ---- M3a: characters / scenes / bind_scene ----
export type CharacterRoleType = "protagonist" | "supporting" | "atmosphere";

export interface CharacterOut {
  id: string;
  name: string;
  role: string;                       // 中文展示值 "主角"/"配角"/"氛围",与后端 role_map 一致
  role_type: CharacterRoleType;       // 原始 ENUM,编辑弹窗下拉用
  is_protagonist: boolean;
  locked: boolean;
  summary: string | null;
  description: string | null;
  meta: string[];                     // 后端已格式化;含 "人像库:Active" 等 tag
  reference_image_url: string | null; // aggregate 层拼好的 OBS 公网 URL
}

export interface CharacterUpdate {
  name?: string;                      // min 1, max 64;显式 null 会被后端 422
  summary?: string | null;
  description?: string | null;
  meta?: Record<string, unknown> | null;
  role_type?: CharacterRoleType;      // 不允许显式 null
}

export interface CharacterGenerateRequest {
  extra_hints?: string[];             // 允许为空;后端 M3a 暂不消费,保留给后续 prompt 增强
}

export interface CharacterLockRequest {
  as_protagonist?: boolean;           // true → 触发后端 lock_protagonist(含人像库入库);false 仅置 locked=true
}

export interface CharacterLockResponse {
  id: string;
  locked: boolean;
  is_protagonist: boolean;
}

export interface GenerateJobAck {
  job_id: string;                     // 主 job;前端只轮询它
  sub_job_ids: string[];              // 子 job 列表,本期只用于调试打印
}

export type SceneThemeRaw = "palace" | "academy" | "harbor" | string | null;

export interface SceneOut {
  id: string;
  name: string;
  theme: SceneThemeRaw;
  locked: boolean;
  summary: string | null;
  description: string | null;
  meta: string[];
  usage: string;                      // "场景复用 N 镜头"
  template_id: string | null;
  reference_image_url: string | null;
}

export interface SceneUpdate {
  name?: string;
  theme?: string;
  summary?: string | null;
  description?: string | null;
  meta?: Record<string, unknown> | null;
  template_id?: string | null;
}

export interface SceneGenerateRequest {
  template_whitelist?: string[];      // 空 = 不限;后端 M3a 暂不消费,保留给后续模板筛选
}

export interface SceneLockRequest {
  // 占位,后端目前无字段,但保留接口形状以便后续扩展
}

export interface SceneLockResponse {
  id: string;
  locked: boolean;
}

export interface BindSceneRequest {
  scene_id: string;
}

export interface BindSceneResponse {
  shot_id: string;
  scene_id: string;
  scene_name: string;
}
```

- [ ] **Step 2: `types/index.ts` 扩展 `CharacterAsset` / `SceneAsset` 以承接 aggregate 新字段**

```ts
/* frontend/src/types/index.ts */
import type {
  CharacterRoleType,
  ProjectStageRaw,
  ProjectStageZh,
  SceneThemeRaw,
  StoryboardDetail
} from "./api";

export type RenderStatus = "success" | "processing" | "warning" | "failed";

/** 分镜卡片展示对象,对齐后端聚合接口与 StoryboardDetail(idx/duration_sec/scene_id 等字段)。 */
export interface StoryboardShot extends StoryboardDetail {}

export interface CharacterAsset {
  id: string;
  name: string;
  role: string;                       // 中文,aggregate 层已拼
  role_type?: CharacterRoleType;      // aggregate M3a 会给;编辑时用
  is_protagonist: boolean;            // M3a 新增
  locked: boolean;                    // M3a 新增
  summary: string | null;
  description: string | null;
  meta: string[];
  reference_image_url?: string | null;  // M3a 新增
}

export interface SceneAsset {
  id: string;
  name: string;
  summary: string | null;
  usage: string;
  description: string | null;
  meta: string[];
  theme: SceneThemeRaw;               // 后端裸字符串 palace/academy/harbor 或 null;CSS class 在组件内映射
  locked: boolean;                    // M3a 新增
  reference_image_url?: string | null;  // M3a 新增
}

export interface RenderQueueItem {
  id: string;
  title: string;
  summary: string;
  status: RenderStatus;
}

export interface ExportTask {
  id: string;
  name: string;
  summary: string;
  status: RenderStatus;
  progressLabel: string;
}

export interface ProjectData {
  id: string;
  name: string;
  stage: ProjectStageZh;
  stage_raw: ProjectStageRaw;
  genre: string | null;
  ratio: string;
  suggestedShots: string;
  story: string;
  summary: string;
  parsedStats: string[];
  setupParams: string[];
  projectOverview: string;
  storyboards: StoryboardShot[];
  characters: CharacterAsset[];
  scenes: SceneAsset[];
  generationProgress: string;
  generationNotes: { input: string; suggestion: string };
  generationQueue: RenderQueueItem[];
  exportConfig: string[];
  exportDuration: string;
  exportTasks: ExportTask[];
}
```

说明:后端 aggregate 返回的 `theme` 是裸字符串(`"palace"` / `"academy"` / `"harbor"` 或空)。前端 demo 的 CSS class 命名是 `theme-palace`/`theme-academy`/`theme-harbor`,映射逻辑放在 Scene 组件内 `computed`,不在 store 里转换(保持 ProjectData 与后端契约一致)。

- [ ] **Step 3: typecheck 验证**

```bash
cd frontend && npm run typecheck
```

Expected: 通过,且触发所有 `CharacterAsset.meta` / `SceneAsset.meta` 使用点类型变化(由 `demo.meta: string[]` → 与后端 `meta: string[]` 一致,无 diff)。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/types/index.ts
git commit -m "feat(frontend): 扩展 CharacterAsset/SceneAsset 以承接 M3a aggregate 新字段"
```

---

## Task 2: `api/characters.ts` 新建 — 5 条 characters 端点

**Files:**
- Create: `frontend/src/api/characters.ts`
- Create: `frontend/tests/unit/characters.api.spec.ts`

- [ ] **Step 1: 写失败测试**

```ts
/* frontend/tests/unit/characters.api.spec.ts */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { client } from "@/api/client";
import { charactersApi } from "@/api/characters";

describe("charactersApi request shape", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("list → GET /projects/:id/characters", async () => {
    const spy = vi.spyOn(client, "get").mockResolvedValue({ data: [] } as never);
    await charactersApi.list("pid");
    expect(spy).toHaveBeenCalledWith("/projects/pid/characters");
  });

  it("generate → POST /projects/:id/characters/generate with body", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J1", sub_job_ids: ["s1", "s2"] }
    } as never);
    const r = await charactersApi.generate("pid", { extra_hints: ["美强惨"] });
    expect(spy).toHaveBeenCalledWith("/projects/pid/characters/generate", {
      extra_hints: ["美强惨"]
    });
    expect(r.job_id).toBe("J1");
    expect(r.sub_job_ids).toEqual(["s1", "s2"]);
  });

  it("update → PATCH /projects/:id/characters/:cid", async () => {
    const spy = vi.spyOn(client, "patch").mockResolvedValue({ data: { id: "c1" } } as never);
    await charactersApi.update("pid", "c1", { summary: "新简介" });
    expect(spy).toHaveBeenCalledWith("/projects/pid/characters/c1", { summary: "新简介" });
  });

  it("regenerate → POST /projects/:id/characters/:cid/regenerate", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J2", sub_job_ids: [] }
    } as never);
    const r = await charactersApi.regenerate("pid", "c1");
    expect(spy).toHaveBeenCalledWith("/projects/pid/characters/c1/regenerate");
    expect(r.job_id).toBe("J2");
  });

  it("lock → POST /projects/:id/characters/:cid/lock with as_protagonist", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { id: "c1", locked: true, is_protagonist: true }
    } as never);
    await charactersApi.lock("pid", "c1", { as_protagonist: true });
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/c1/lock",
      { as_protagonist: true },
      { timeout: 150_000 }
    );
  });
});
```

- [ ] **Step 2: 跑测试,预期失败(文件不存在)**

```bash
cd frontend && npm test -- characters.api
```

Expected: 全红(`Cannot find module '@/api/characters'`)。

- [ ] **Step 3: 实现 `api/characters.ts`**

```ts
/* frontend/src/api/characters.ts */
import { client } from "./client";
import type {
  CharacterOut,
  CharacterUpdate,
  CharacterGenerateRequest,
  CharacterLockRequest,
  CharacterLockResponse,
  GenerateJobAck
} from "@/types/api";

// 主角锁定会同步调用后端人像库 CreateAsset + wait_asset_active(默认 120s);
// 前端给这一条单独放宽到 150s,避开默认 15s 超时。
const LOCK_TIMEOUT_MS = 150_000;

export const charactersApi = {
  list(projectId: string): Promise<CharacterOut[]> {
    return client
      .get(`/projects/${projectId}/characters`)
      .then((r) => r.data as CharacterOut[]);
  },
  generate(
    projectId: string,
    payload: CharacterGenerateRequest = {}
  ): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/characters/generate`, payload)
      .then((r) => r.data as GenerateJobAck);
  },
  update(
    projectId: string,
    characterId: string,
    payload: CharacterUpdate
  ): Promise<CharacterOut> {
    return client
      .patch(`/projects/${projectId}/characters/${characterId}`, payload)
      .then((r) => r.data as CharacterOut);
  },
  regenerate(projectId: string, characterId: string): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/characters/${characterId}/regenerate`)
      .then((r) => r.data as GenerateJobAck);
  },
  lock(
    projectId: string,
    characterId: string,
    payload: CharacterLockRequest
  ): Promise<CharacterLockResponse> {
    return client
      .post(`/projects/${projectId}/characters/${characterId}/lock`, payload, {
        timeout: LOCK_TIMEOUT_MS
      })
      .then((r) => r.data as CharacterLockResponse);
  }
};
```

- [ ] **Step 4: 跑测试通过**

```bash
cd frontend && npm test -- characters.api
```

Expected: 5 条 test 全绿。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/characters.ts frontend/tests/unit/characters.api.spec.ts
git commit -m "feat(frontend): characters api client + 请求拼装测试"
```

---

## Task 3: `api/scenes.ts` 新建 + `storyboards.ts.bindScene` 扩展

**Files:**
- Create: `frontend/src/api/scenes.ts`
- Modify: `frontend/src/api/storyboards.ts`
- Create: `frontend/tests/unit/scenes.api.spec.ts`

- [ ] **Step 1: 写失败测试**

```ts
/* frontend/tests/unit/scenes.api.spec.ts */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { client } from "@/api/client";
import { scenesApi } from "@/api/scenes";
import { storyboardsApi } from "@/api/storyboards";

describe("scenesApi request shape", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("list → GET /projects/:id/scenes", async () => {
    const spy = vi.spyOn(client, "get").mockResolvedValue({ data: [] } as never);
    await scenesApi.list("pid");
    expect(spy).toHaveBeenCalledWith("/projects/pid/scenes");
  });

  it("generate → POST /projects/:id/scenes/generate with body", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J1", sub_job_ids: [] }
    } as never);
    await scenesApi.generate("pid", { template_whitelist: ["palace"] });
    expect(spy).toHaveBeenCalledWith("/projects/pid/scenes/generate", {
      template_whitelist: ["palace"]
    });
  });

  it("update → PATCH /projects/:id/scenes/:sid", async () => {
    const spy = vi.spyOn(client, "patch").mockResolvedValue({ data: {} } as never);
    await scenesApi.update("pid", "s1", { name: "长安殿" });
    expect(spy).toHaveBeenCalledWith("/projects/pid/scenes/s1", { name: "长安殿" });
  });

  it("regenerate → POST /projects/:id/scenes/:sid/regenerate", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J2", sub_job_ids: [] }
    } as never);
    await scenesApi.regenerate("pid", "s1");
    expect(spy).toHaveBeenCalledWith("/projects/pid/scenes/s1/regenerate");
  });

  it("lock → POST /projects/:id/scenes/:sid/lock", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { id: "s1", locked: true }
    } as never);
    await scenesApi.lock("pid", "s1");
    expect(spy).toHaveBeenCalledWith("/projects/pid/scenes/s1/lock", {});
  });
});

describe("storyboardsApi.bindScene", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("POST /projects/:id/storyboards/:shot/bind_scene with scene_id", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { shot_id: "sh1", scene_id: "sc1", scene_name: "长安殿" }
    } as never);
    const r = await storyboardsApi.bindScene("pid", "sh1", { scene_id: "sc1" });
    expect(spy).toHaveBeenCalledWith("/projects/pid/storyboards/sh1/bind_scene", {
      scene_id: "sc1"
    });
    expect(r.scene_name).toBe("长安殿");
  });
});
```

- [ ] **Step 2: 跑测试预期失败**

```bash
cd frontend && npm test -- scenes.api
```

Expected: 全红。

- [ ] **Step 3: 实现 `api/scenes.ts`**

```ts
/* frontend/src/api/scenes.ts */
import { client } from "./client";
import type {
  SceneOut,
  SceneUpdate,
  SceneGenerateRequest,
  SceneLockRequest,
  SceneLockResponse,
  GenerateJobAck
} from "@/types/api";

export const scenesApi = {
  list(projectId: string): Promise<SceneOut[]> {
    return client.get(`/projects/${projectId}/scenes`).then((r) => r.data as SceneOut[]);
  },
  generate(projectId: string, payload: SceneGenerateRequest = {}): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/scenes/generate`, payload)
      .then((r) => r.data as GenerateJobAck);
  },
  update(projectId: string, sceneId: string, payload: SceneUpdate): Promise<SceneOut> {
    return client
      .patch(`/projects/${projectId}/scenes/${sceneId}`, payload)
      .then((r) => r.data as SceneOut);
  },
  regenerate(projectId: string, sceneId: string): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/scenes/${sceneId}/regenerate`)
      .then((r) => r.data as GenerateJobAck);
  },
  lock(projectId: string, sceneId: string, payload: SceneLockRequest = {}): Promise<SceneLockResponse> {
    return client
      .post(`/projects/${projectId}/scenes/${sceneId}/lock`, payload)
      .then((r) => r.data as SceneLockResponse);
  }
};
```

- [ ] **Step 4: 扩展 `api/storyboards.ts` 末尾追加 `bindScene`**

```ts
// 追加到 storyboardsApi 对象末尾(注意补前一项的结尾逗号)
bindScene(
  projectId: string,
  shotId: string,
  payload: BindSceneRequest
): Promise<BindSceneResponse> {
  return client
    .post(`/projects/${projectId}/storyboards/${shotId}/bind_scene`, payload)
    .then((r) => r.data as BindSceneResponse);
}
```

同时在文件顶部 import 补:

```ts
import type {
  BindSceneRequest,
  BindSceneResponse,
  // ... 其余已有 import
} from "@/types/api";
```

- [ ] **Step 5: 跑测试通过**

```bash
cd frontend && npm test -- scenes.api
```

Expected: 6 条 test 全绿。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/scenes.ts frontend/src/api/storyboards.ts frontend/tests/unit/scenes.api.spec.ts
git commit -m "feat(frontend): scenes api + storyboards.bindScene"
```

---

## Task 4: `composables/useStageGate.ts` 扩展 — 新增 M3a flag

**Files:**
- Modify: `frontend/src/composables/useStageGate.ts`
- Modify: `frontend/tests/unit/useStageGate.spec.ts`

- [ ] **Step 1: 改实现**

```ts
/* frontend/src/composables/useStageGate.ts */
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import type { ProjectStageRaw } from "@/types/api";

export interface StageGateFlags {
  canEditStoryboards: boolean;
  canGenerateCharacters: boolean;
  canGenerateScenes: boolean;
  canEditCharacters: boolean;   // M3a 新增:角色编辑窗口(严格对齐后端 assert_asset_editable("character") = storyboard_ready)
  canEditScenes: boolean;       // M3a 新增:scenes 编辑窗口(= characters_locked)
  canBindScene: boolean;        // M3a 新增:bind_scene 仅在 characters_locked 允许
  canLockCharacter: boolean;    // M3a 新增:lock 接口后端要求 stage_raw ∈ {storyboard_ready}
  canLockScene: boolean;        // M3a 新增:lock scene 要求 stage_raw ∈ {characters_locked}
  canRender: boolean;
  canExport: boolean;
  canLockShot: boolean;
  canRollback: boolean;
}

export function gateFlags(raw: ProjectStageRaw | null | undefined): StageGateFlags {
  const isStoryboardReady = raw === "storyboard_ready";
  const isCharactersLocked = raw === "characters_locked";
  return {
    canEditStoryboards: raw === "draft" || isStoryboardReady,
    canGenerateCharacters: isStoryboardReady,
    canGenerateScenes: isCharactersLocked,
    canEditCharacters: isStoryboardReady,
    canEditScenes: isCharactersLocked,
    canBindScene: isCharactersLocked,
    canLockCharacter: isStoryboardReady,
    canLockScene: isCharactersLocked,
    canRender: raw === "scenes_locked" || raw === "rendering",
    canExport: raw === "ready_for_export",
    canLockShot: raw === "rendering" || raw === "ready_for_export",
    canRollback: !!raw && raw !== "draft"
  };
}

export function useStageGate() {
  const { current } = storeToRefs(useWorkbenchStore());
  const flags = computed(() => gateFlags(current.value?.stage_raw ?? null));
  return { flags };
}
```

- [ ] **Step 2: 补充 useStageGate 单元测试**

```ts
// 在现有 tests/unit/useStageGate.spec.ts 末尾追加
import { gateFlags } from "@/composables/useStageGate";

describe("M3a gates", () => {
  it("storyboard_ready: can edit/lock/generate characters, not scenes", () => {
    const f = gateFlags("storyboard_ready");
    expect(f.canEditCharacters).toBe(true);
    expect(f.canLockCharacter).toBe(true);
    expect(f.canGenerateCharacters).toBe(true);
    expect(f.canEditScenes).toBe(false);
    expect(f.canBindScene).toBe(false);
    expect(f.canLockScene).toBe(false);
    expect(f.canGenerateScenes).toBe(false);
  });

  it("characters_locked: can edit/lock/generate/bind scenes, not characters", () => {
    const f = gateFlags("characters_locked");
    expect(f.canEditCharacters).toBe(false);
    expect(f.canLockCharacter).toBe(false);
    expect(f.canGenerateCharacters).toBe(false);
    expect(f.canEditScenes).toBe(true);
    expect(f.canBindScene).toBe(true);
    expect(f.canLockScene).toBe(true);
    expect(f.canGenerateScenes).toBe(true);
  });

  it("scenes_locked and later: neither character nor scene edits allowed", () => {
    const raws = ["scenes_locked", "rendering", "ready_for_export", "exported"] as const;
    for (const r of raws) {
      const f = gateFlags(r);
      expect(f.canEditCharacters).toBe(false);
      expect(f.canEditScenes).toBe(false);
      expect(f.canLockCharacter).toBe(false);
      expect(f.canLockScene).toBe(false);
      expect(f.canBindScene).toBe(false);
    }
  });
});
```

- [ ] **Step 3: Commit**

```bash
cd frontend && npm test -- useStageGate
git add frontend/src/composables/useStageGate.ts frontend/tests/unit/useStageGate.spec.ts
git commit -m "feat(frontend): useStageGate 增 canEditCharacters/canEditScenes/canBindScene/canLockCharacter/canLockScene"
```

Expected: 测试全绿。

---

## Task 5: `utils/error.ts` — 42201 "AI 内容违规" 映射

**Files:**
- Modify: `frontend/src/utils/error.ts`
- Modify: `frontend/src/types/api.ts`(ERROR_CODE 常量)
- Modify: `frontend/tests/unit/error.spec.ts`

- [ ] **Step 1: `types/api.ts` 的 ERROR_CODE 常量增加 `CONTENT_FILTER`**

```ts
// 找到现有的 ERROR_CODE 定义并扩展:
export const ERROR_CODE = {
  VALIDATION: 40001,
  STAGE_FORBIDDEN: 40301,
  NOT_FOUND: 40401,
  CONFLICT: 40901,
  RATE_LIMIT: 42901,
  CONTENT_FILTER: 42201,   // ← 新增(M3a)
  INTERNAL: 50001,
  UPSTREAM: 50301
} as const;
```

- [ ] **Step 2: `utils/error.ts` 的 TEXT 表增加 42201 文案**

```ts
const TEXT: Record<number, string> = {
  [ERROR_CODE.VALIDATION]: "参数不合法,请检查后重试",
  [ERROR_CODE.STAGE_FORBIDDEN]: "当前阶段不允许该操作",
  [ERROR_CODE.NOT_FOUND]: "资源不存在或已被删除",
  [ERROR_CODE.CONFLICT]: "业务冲突,请刷新后重试",
  [ERROR_CODE.RATE_LIMIT]: "AI 限流,请稍后重试",
  [ERROR_CODE.CONTENT_FILTER]: "AI 内容违规,请修改文案后重试",   // ← 新增(M3a)
  [ERROR_CODE.INTERNAL]: "服务异常,请稍后再试",
  [ERROR_CODE.UPSTREAM]: "上游服务异常,请稍后再试"
};
```

- [ ] **Step 3: 测试追加**

```ts
// tests/unit/error.spec.ts 末尾追加
it("maps 42201 to '内容违规' text", () => {
  expect(messageFor(42201)).toContain("内容违规");
});
```

- [ ] **Step 4: 跑测试通过 + commit**

```bash
cd frontend && npm test -- error
git add frontend/src/types/api.ts frontend/src/utils/error.ts frontend/tests/unit/error.spec.ts
git commit -m "feat(frontend): 42201 内容违规错误码映射"
```

---

## Task 6: `store/workbench.ts` — 新增 M3a 写动作 + job 追踪

**Files:**
- Modify: `frontend/src/store/workbench.ts`
- Create: `frontend/tests/unit/workbench.m3a.store.spec.ts`

设计要点:

- 主 job 追踪:`activeGenerateCharactersJobId` / `activeGenerateScenesJobId`(ref<{projectId, jobId} | null>,和 parseJob 同构);computed 派生避免跨项目串台
- 单项 regen 的 job 追踪:`regenJobs: ref<Record<string, { projectId: string; jobId: string }>>` key = `"character:<id>"` / `"scene:<id>"`;UI 通过 `regenJobIdFor(kind,id)` 读取,避免跨项目串台;同时提供 `activeRegenJobEntries` 给面板轮询当前项目内的 active regen job。M3a 同一 panel 同时只允许一个同类 regen job,有 active character regen 时禁用所有角色重生成按钮,有 active scene regen 时禁用所有场景重生成按钮。
- 每条写动作 try/成功 reload/失败抛出 原则照搬 M2
- `lockCharacter`:传入 `as_protagonist` 直接透传;后端会在同一请求内同步做 `ensure_character_asset_registered`(最多 ~120s),所以 action 本身不等 job,只等 HTTP 返回 → reload
- `bindShotScene`:选中 shot + 选中 scene 即可,不要求所有 shot 一次性绑全(后端 lock scene 时会校验并在未全部 bind 完时不推进 stage,UI 保持当前 stage 显示即可)

- [ ] **Step 1: 写失败测试(覆盖关键动作)**

```ts
/* frontend/tests/unit/workbench.m3a.store.spec.ts */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import { projectsApi } from "@/api/projects";
import { charactersApi } from "@/api/characters";
import { scenesApi } from "@/api/scenes";
import { storyboardsApi } from "@/api/storyboards";

const mkProject = (overrides: Partial<import("@/types").ProjectData> = {}) => ({
  id: "P1",
  name: "Demo",
  stage: "分镜已生成" as const,
  stage_raw: "storyboard_ready" as const,
  genre: "古风权谋",
  ratio: "9:16",
  suggestedShots: "",
  story: "",
  summary: "",
  parsedStats: [],
  setupParams: [],
  projectOverview: "",
  storyboards: [{
    id: "SH1",
    idx: 1,
    title: "开场",
    description: "",
    detail: "",
    duration_sec: 3,
    tags: [],
    status: "pending",
    scene_id: null,
    current_render_id: null,
    created_at: "2026-04-21T00:00:00Z",
    updated_at: "2026-04-21T00:00:00Z"
  }],
  characters: [],
  scenes: [],
  generationProgress: "",
  generationNotes: { input: "", suggestion: "" },
  generationQueue: [],
  exportConfig: [],
  exportDuration: "",
  exportTasks: [],
  ...overrides
});

describe("workbench M3a actions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("generateCharacters: 写入 activeGenerateCharactersJobId 并返回 job_id", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject());
    vi.spyOn(charactersApi, "generate").mockResolvedValue({
      job_id: "J1",
      sub_job_ids: ["s1", "s2"]
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.generateCharacters({ extra_hints: [] });
    expect(jobId).toBe("J1");
    expect(store.activeGenerateCharactersJobId).toBe("J1");
  });

  it("lockCharacter(as_protagonist=true) 成功后 reload", async () => {
    const getSpy = vi
      .spyOn(projectsApi, "get")
      .mockResolvedValueOnce(mkProject({
        characters: [{
          id: "C1", name: "秦昭", role: "配角", is_protagonist: false,
          locked: false, summary: "", description: "", meta: [], reference_image_url: null
        }]
      }))
      .mockResolvedValueOnce(mkProject({
        stage: "角色已锁定",
        stage_raw: "characters_locked",
        characters: [{
          id: "C1", name: "秦昭", role: "主角", is_protagonist: true,
          locked: true, summary: "", description: "", meta: ["人像库:Active"],
          reference_image_url: "https://static/x.png"
        }]
      }));
    const lockSpy = vi.spyOn(charactersApi, "lock").mockResolvedValue({
      id: "C1",
      locked: true,
      is_protagonist: true
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.lockCharacter("C1", { as_protagonist: true });
    expect(lockSpy).toHaveBeenCalledWith("P1", "C1", { as_protagonist: true });
    expect(getSpy).toHaveBeenCalledTimes(2);  // load + reload
    expect(store.current?.stage_raw).toBe("characters_locked");
  });

  it("regenerateCharacter: 单项 job 记在 regenJobs['character:<id>']", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      characters: [{
        id: "C1", name: "秦昭", role: "主角", is_protagonist: false,
        locked: false, summary: "", description: "", meta: [], reference_image_url: null
      }]
    }));
    vi.spyOn(charactersApi, "regenerate").mockResolvedValue({
      job_id: "RJ1", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.regenerateCharacter("C1");
    expect(jobId).toBe("RJ1");
    expect(store.regenJobIdFor("character", "C1")).toBe("RJ1");
    expect(store.activeRegenJobEntries).toEqual([{ key: "character:C1", jobId: "RJ1" }]);
    store.markRegenByKeySucceeded("character:C1");
    expect(store.regenJobIdFor("character", "C1")).toBeNull();
  });

  it("regenerateCharacter: 同一项目已有角色重生成时拒绝并发", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      characters: [
        { id: "C1", name: "秦昭", role: "主角", is_protagonist: false, locked: false, summary: "", description: "", meta: [], reference_image_url: null },
        { id: "C2", name: "江离", role: "配角", is_protagonist: false, locked: false, summary: "", description: "", meta: [], reference_image_url: null }
      ]
    }));
    vi.spyOn(charactersApi, "regenerate").mockResolvedValue({
      job_id: "RJ1", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.regenerateCharacter("C1");
    await expect(store.regenerateCharacter("C2")).rejects.toMatchObject({
      code: 40901,
      message: "已有角色重生成任务进行中"
    });
  });

  it("bindShotScene: POST + reload", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "角色已锁定",
      stage_raw: "characters_locked"
    }));
    const bindSpy = vi.spyOn(storyboardsApi, "bindScene").mockResolvedValue({
      shot_id: "SH1", scene_id: "SC1", scene_name: "长安殿"
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.bindShotScene("SH1", "SC1");
    expect(bindSpy).toHaveBeenCalledWith("P1", "SH1", { scene_id: "SC1" });
  });

  it("generateScenes: 写入 activeGenerateScenesJobId", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "角色已锁定",
      stage_raw: "characters_locked"
    }));
    vi.spyOn(scenesApi, "generate").mockResolvedValue({
      job_id: "J2", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.generateScenes({ template_whitelist: [] });
    expect(jobId).toBe("J2");
    expect(store.activeGenerateScenesJobId).toBe("J2");
  });

  it("regenerateScene: 同一项目已有场景重生成时拒绝并发", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "角色已锁定",
      stage_raw: "characters_locked",
      scenes: [
        { id: "S1", name: "长安殿", theme: "palace", summary: "", usage: "", description: "", meta: [], locked: false, reference_image_url: null },
        { id: "S2", name: "御花园", theme: "palace", summary: "", usage: "", description: "", meta: [], locked: false, reference_image_url: null }
      ]
    }));
    vi.spyOn(scenesApi, "regenerate").mockResolvedValue({
      job_id: "SRJ1", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.regenerateScene("S1");
    await expect(store.regenerateScene("S2")).rejects.toMatchObject({
      code: 40901,
      message: "已有场景重生成任务进行中"
    });
  });
});
```

- [ ] **Step 2: 跑测试预期失败**

```bash
cd frontend && npm test -- workbench.m3a
```

Expected: 全红(动作/字段未实现)。

- [ ] **Step 3: 实现 store 扩展**

在 `store/workbench.ts` 现有基础上追加(完整替换文件,保持 M2 动作不动):

```ts
/* frontend/src/store/workbench.ts — M3a 扩展 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { projectsApi } from "@/api/projects";
import { storyboardsApi } from "@/api/storyboards";
import { charactersApi } from "@/api/characters";
import { scenesApi } from "@/api/scenes";
import { ApiError } from "@/utils/error";
import type { ProjectData } from "@/types";
import type {
  ProjectRollbackRequest,
  ProjectRollbackResponse,
  StoryboardConfirmResponse,
  StoryboardCreateRequest,
  StoryboardUpdateRequest,
  CharacterGenerateRequest,
  CharacterLockRequest,
  CharacterUpdate,
  SceneGenerateRequest,
  SceneUpdate
} from "@/types/api";

export type WorkflowStep = "setup" | "storyboard" | "character" | "scene" | "render" | "export";
export type RegenKind = "character" | "scene";

export const useWorkbenchStore = defineStore("workbench", () => {
  const current = ref<ProjectData | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const selectedShotId = ref<string>("");
  const selectedCharacterId = ref<string>("");
  const selectedSceneId = ref<string>("");
  const activeStep = ref<WorkflowStep>("setup");

  // ---- job 追踪(均按 projectId 作用域)----
  const parseJob = ref<{ projectId: string; jobId: string } | null>(null);
  const parseError = ref<string | null>(null);

  const generateCharactersJob = ref<{ projectId: string; jobId: string } | null>(null);
  const generateCharactersError = ref<string | null>(null);

  const generateScenesJob = ref<{ projectId: string; jobId: string } | null>(null);
  const generateScenesError = ref<string | null>(null);

  // 单项 regen: key = "<kind>:<id>";value = jobId
  const regenJobs = ref<Record<string, { projectId: string; jobId: string }>>({});

  function scopedJobId(
    scope: { projectId: string; jobId: string } | null
  ): string | null {
    if (!scope || !current.value || scope.projectId !== current.value.id) return null;
    return scope.jobId;
  }

  const activeParseJobId = computed<string | null>(() => scopedJobId(parseJob.value));
  const activeGenerateCharactersJobId = computed<string | null>(() =>
    scopedJobId(generateCharactersJob.value)
  );
  const activeGenerateScenesJobId = computed<string | null>(() =>
    scopedJobId(generateScenesJob.value)
  );

  function regenJobIdFor(kind: RegenKind, id: string): string | null {
    const rec = regenJobs.value[`${kind}:${id}`];
    return scopedJobId(rec ?? null);
  }
  const activeRegenJobEntries = computed(() =>
    Object.entries(regenJobs.value)
      .filter(([, rec]) => current.value && rec.projectId === current.value.id)
      .map(([key, rec]) => ({ key, jobId: rec.jobId }))
  );
  function hasActiveRegen(kind: RegenKind): boolean {
    return activeRegenJobEntries.value.some((entry) => entry.key.startsWith(`${kind}:`));
  }

  // ---- 派生选择器 ----
  const currentShot = computed(
    () =>
      current.value?.storyboards.find((s) => s.id === selectedShotId.value) ??
      current.value?.storyboards[0] ??
      null
  );
  const selectedCharacter = computed(
    () =>
      current.value?.characters.find((c) => c.id === selectedCharacterId.value) ??
      current.value?.characters[0] ??
      null
  );
  const selectedScene = computed(
    () =>
      current.value?.scenes.find((s) => s.id === selectedSceneId.value) ??
      current.value?.scenes[0] ??
      null
  );

  // ---- 核心 load/reload/rollback(M1/M2,保持) ----
  async function load(id: string) {
    loading.value = true;
    error.value = null;
    try {
      current.value = await projectsApi.get(id);
      if (!current.value.storyboards.some((s) => s.id === selectedShotId.value)) {
        selectedShotId.value = current.value.storyboards[0]?.id ?? "";
      }
      if (!current.value.characters.some((c) => c.id === selectedCharacterId.value)) {
        selectedCharacterId.value = current.value.characters[0]?.id ?? "";
      }
      if (!current.value.scenes.some((s) => s.id === selectedSceneId.value)) {
        selectedSceneId.value = current.value.scenes[0]?.id ?? "";
      }
    } catch (e) {
      error.value = (e as Error).message;
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function reload() {
    if (current.value) await load(current.value.id);
  }

  async function rollback(payload: ProjectRollbackRequest): Promise<ProjectRollbackResponse> {
    if (!current.value) throw new Error("no current project");
    const resp = await projectsApi.rollback(current.value.id, payload);
    await reload();
    return resp;
  }

  // ---- M2 动作(保持) ----
  async function startParse(projectId?: string): Promise<string> {
    const pid = projectId ?? current.value?.id;
    if (!pid) throw new Error("startParse: no project id");
    parseError.value = null;
    const resp = await projectsApi.parse(pid);
    parseJob.value = { projectId: pid, jobId: resp.job_id };
    return resp.job_id;
  }
  function markParseSucceeded() { parseJob.value = null; parseError.value = null; }
  function markParseFailed(msg: string) { parseJob.value = null; parseError.value = msg; }

  async function createShot(payload: StoryboardCreateRequest) {
    if (!current.value) throw new Error("createShot: no current project");
    await storyboardsApi.create(current.value.id, payload);
    await reload();
  }
  async function updateShot(shotId: string, payload: StoryboardUpdateRequest) {
    if (!current.value) throw new Error("updateShot: no current project");
    await storyboardsApi.update(current.value.id, shotId, payload);
    await reload();
  }
  async function deleteShot(shotId: string) {
    if (!current.value) throw new Error("deleteShot: no current project");
    await storyboardsApi.remove(current.value.id, shotId);
    if (selectedShotId.value === shotId) selectedShotId.value = "";
    await reload();
  }
  async function reorderShots(orderedIds: string[]) {
    if (!current.value) throw new Error("reorderShots: no current project");
    await storyboardsApi.reorder(current.value.id, { ordered_ids: orderedIds });
    await reload();
  }
  async function moveShotUp(shotId: string) {
    if (!current.value) return;
    const ids = current.value.storyboards.map((s) => s.id);
    const i = ids.indexOf(shotId);
    if (i <= 0) return;
    [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]];
    await reorderShots(ids);
  }
  async function moveShotDown(shotId: string) {
    if (!current.value) return;
    const ids = current.value.storyboards.map((s) => s.id);
    const i = ids.indexOf(shotId);
    if (i < 0 || i >= ids.length - 1) return;
    [ids[i], ids[i + 1]] = [ids[i + 1], ids[i]];
    await reorderShots(ids);
  }
  async function confirmStoryboards(): Promise<StoryboardConfirmResponse> {
    if (!current.value) throw new Error("confirmStoryboards: no current project");
    const resp = await storyboardsApi.confirm(current.value.id);
    await reload();
    return resp;
  }

  // ---- M3a 写动作 ----
  async function generateCharacters(payload: CharacterGenerateRequest = {}): Promise<string> {
    if (!current.value) throw new Error("generateCharacters: no current project");
    generateCharactersError.value = null;
    const ack = await charactersApi.generate(current.value.id, payload);
    generateCharactersJob.value = { projectId: current.value.id, jobId: ack.job_id };
    return ack.job_id;
  }
  function markGenerateCharactersSucceeded() {
    generateCharactersJob.value = null;
    generateCharactersError.value = null;
  }
  function markGenerateCharactersFailed(msg: string) {
    generateCharactersJob.value = null;
    generateCharactersError.value = msg;
  }

  async function patchCharacter(characterId: string, payload: CharacterUpdate) {
    if (!current.value) throw new Error("patchCharacter: no current project");
    await charactersApi.update(current.value.id, characterId, payload);
    await reload();
  }

  async function regenerateCharacter(characterId: string): Promise<string> {
    if (!current.value) throw new Error("regenerateCharacter: no current project");
    if (hasActiveRegen("character")) {
      throw new ApiError(40901, "已有角色重生成任务进行中");
    }
    const ack = await charactersApi.regenerate(current.value.id, characterId);
    regenJobs.value[`character:${characterId}`] = {
      projectId: current.value.id,
      jobId: ack.job_id
    };
    return ack.job_id;
  }

  async function lockCharacter(characterId: string, payload: CharacterLockRequest) {
    if (!current.value) throw new Error("lockCharacter: no current project");
    await charactersApi.lock(current.value.id, characterId, payload);
    await reload();
  }

  async function generateScenes(payload: SceneGenerateRequest = {}): Promise<string> {
    if (!current.value) throw new Error("generateScenes: no current project");
    generateScenesError.value = null;
    const ack = await scenesApi.generate(current.value.id, payload);
    generateScenesJob.value = { projectId: current.value.id, jobId: ack.job_id };
    return ack.job_id;
  }
  function markGenerateScenesSucceeded() {
    generateScenesJob.value = null;
    generateScenesError.value = null;
  }
  function markGenerateScenesFailed(msg: string) {
    generateScenesJob.value = null;
    generateScenesError.value = msg;
  }

  async function patchScene(sceneId: string, payload: SceneUpdate) {
    if (!current.value) throw new Error("patchScene: no current project");
    await scenesApi.update(current.value.id, sceneId, payload);
    await reload();
  }

  async function regenerateScene(sceneId: string): Promise<string> {
    if (!current.value) throw new Error("regenerateScene: no current project");
    if (hasActiveRegen("scene")) {
      throw new ApiError(40901, "已有场景重生成任务进行中");
    }
    const ack = await scenesApi.regenerate(current.value.id, sceneId);
    regenJobs.value[`scene:${sceneId}`] = {
      projectId: current.value.id,
      jobId: ack.job_id
    };
    return ack.job_id;
  }

  async function lockScene(sceneId: string) {
    if (!current.value) throw new Error("lockScene: no current project");
    await scenesApi.lock(current.value.id, sceneId, {});
    await reload();
  }

  async function bindShotScene(shotId: string, sceneId: string) {
    if (!current.value) throw new Error("bindShotScene: no current project");
    await storyboardsApi.bindScene(current.value.id, shotId, { scene_id: sceneId });
    await reload();
  }

  function markRegenSucceeded(kind: RegenKind, id: string) {
    delete regenJobs.value[`${kind}:${id}`];
  }
  function markRegenFailed(kind: RegenKind, id: string) {
    delete regenJobs.value[`${kind}:${id}`];
  }
  function markRegenByKeySucceeded(key: string) {
    delete regenJobs.value[key];
  }
  function markRegenByKeyFailed(key: string) {
    delete regenJobs.value[key];
  }

  // ---- selectors ----
  function selectShot(id: string) { selectedShotId.value = id; }
  function selectCharacter(id: string) { selectedCharacterId.value = id; }
  function selectScene(id: string) { selectedSceneId.value = id; }
  function setStep(step: WorkflowStep) { activeStep.value = step; }

  return {
    current, loading, error,
    selectedShotId, selectedCharacterId, selectedSceneId, activeStep,
    activeParseJobId, parseError,
    activeGenerateCharactersJobId, generateCharactersError,
    activeGenerateScenesJobId, generateScenesError,
    regenJobIdFor, activeRegenJobEntries,
    currentShot, selectedCharacter, selectedScene,
    load, reload, rollback,
    startParse, markParseSucceeded, markParseFailed,
    createShot, updateShot, deleteShot, reorderShots, moveShotUp, moveShotDown, confirmStoryboards,
    generateCharacters, markGenerateCharactersSucceeded, markGenerateCharactersFailed,
    patchCharacter, regenerateCharacter, lockCharacter,
    generateScenes, markGenerateScenesSucceeded, markGenerateScenesFailed,
    patchScene, regenerateScene, lockScene, bindShotScene,
    markRegenSucceeded, markRegenFailed, markRegenByKeySucceeded, markRegenByKeyFailed,
    selectShot, selectCharacter, selectScene, setStep
  };
});
```

- [ ] **Step 4: 测试通过 + commit**

```bash
cd frontend && npm test -- workbench
git add frontend/src/store/workbench.ts frontend/tests/unit/workbench.m3a.store.spec.ts
git commit -m "feat(frontend): workbench store 增 M3a 写动作与 job 追踪"
```

Expected: 所有 workbench spec 绿。

---

## Task 7: `CharacterEditorModal.vue` 新组件

**Files:**
- Create: `frontend/src/components/character/CharacterEditorModal.vue`

用于 `CharacterAssetsPanel` 的 "编辑描述" 按钮。表单字段:`name` / `role_type`(下拉)/ `summary` / `description`。

- [ ] **Step 1: 实现**

```vue
<!-- frontend/src/components/character/CharacterEditorModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "@/components/common/Modal.vue";
import type { CharacterRoleType, CharacterUpdate } from "@/types/api";
import type { CharacterAsset } from "@/types";

const props = defineProps<{
  open: boolean;
  character: CharacterAsset | null;
  busy?: boolean;
}>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: CharacterUpdate): void;
}>();

const ROLE_OPTIONS: { value: CharacterRoleType; label: string }[] = [
  { value: "protagonist", label: "主角" },
  { value: "supporting", label: "配角" },
  { value: "atmosphere", label: "氛围" }
];

const name = ref("");
const roleType = ref<CharacterRoleType>("supporting");
const summary = ref("");
const description = ref("");
const validationError = ref<string | null>(null);

watch(
  () => props.open,
  (open) => {
    if (open && props.character) {
      name.value = props.character.name;
      roleType.value = (props.character.role_type ?? "supporting") as CharacterRoleType;
      summary.value = props.character.summary ?? "";
      description.value = props.character.description ?? "";
      validationError.value = null;
    }
  },
  { immediate: true }
);

const canSubmit = computed(() => !!name.value.trim() && !props.busy);

function submit() {
  const trimmedName = name.value.trim();
  if (!trimmedName) {
    validationError.value = "名称不能为空";
    return;
  }
  if (trimmedName.length > 64) {
    validationError.value = "名称不能超过 64 字";
    return;
  }
  emit("submit", {
    name: trimmedName,
    role_type: roleType.value,
    summary: summary.value.trim() || null,
    description: description.value.trim() || null
  });
}
</script>

<template>
  <Modal :open="open" title="编辑角色" @close="emit('close')">
    <form class="character-form" @submit.prevent="submit">
      <label>
        <span>角色名</span>
        <input v-model="name" type="text" maxlength="64" required />
      </label>
      <label>
        <span>角色类型</span>
        <select v-model="roleType">
          <option v-for="opt in ROLE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>
      <label>
        <span>简介(255 字以内)</span>
        <input v-model="summary" type="text" maxlength="255" />
      </label>
      <label>
        <span>详细描述</span>
        <textarea v-model="description" rows="5" />
      </label>
      <p v-if="validationError" class="form-error">{{ validationError }}</p>
      <div class="form-actions">
        <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
        <button class="primary-btn" type="submit" :disabled="!canSubmit">
          {{ busy ? "保存中..." : "保存" }}
        </button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.character-form { display: flex; flex-direction: column; gap: 14px; }
.character-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.character-form input, .character-form select, .character-form textarea {
  padding: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}
.form-error { color: var(--danger); font-size: 12px; margin: 0; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
</style>
```

- [ ] **Step 2: typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: 通过。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/character/CharacterEditorModal.vue
git commit -m "feat(frontend): CharacterEditorModal 角色编辑弹窗"
```

---

## Task 8: `SceneEditorModal.vue` 新组件

**Files:**
- Create: `frontend/src/components/scene/SceneEditorModal.vue`

- [ ] **Step 1: 实现**

```vue
<!-- frontend/src/components/scene/SceneEditorModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "@/components/common/Modal.vue";
import type { SceneUpdate } from "@/types/api";
import type { SceneAsset } from "@/types";

const props = defineProps<{
  open: boolean;
  scene: SceneAsset | null;
  busy?: boolean;
}>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: SceneUpdate): void;
}>();

const name = ref("");
const theme = ref("");
const summary = ref("");
const description = ref("");
const validationError = ref<string | null>(null);

watch(
  () => props.open,
  (open) => {
    if (open && props.scene) {
      name.value = props.scene.name;
      theme.value = props.scene.theme ?? "";
      summary.value = props.scene.summary ?? "";
      description.value = props.scene.description ?? "";
      validationError.value = null;
    }
  },
  { immediate: true }
);

const canSubmit = computed(() => !!name.value.trim() && !props.busy);

function submit() {
  const trimmedName = name.value.trim();
  if (!trimmedName) {
    validationError.value = "名称不能为空";
    return;
  }
  if (trimmedName.length > 64) {
    validationError.value = "名称不能超过 64 字";
    return;
  }
  const payload: SceneUpdate = {
    name: trimmedName,
    summary: summary.value.trim() || null,
    description: description.value.trim() || null
  };
  // theme 为空串时不传(避免显式 null 被后端 422)
  if (theme.value.trim()) payload.theme = theme.value.trim();
  emit("submit", payload);
}
</script>

<template>
  <Modal :open="open" title="编辑场景" @close="emit('close')">
    <form class="scene-form" @submit.prevent="submit">
      <label>
        <span>场景名</span>
        <input v-model="name" type="text" maxlength="64" required />
      </label>
      <label>
        <span>主题(可选)</span>
        <input v-model="theme" type="text" maxlength="32" placeholder="palace / academy / harbor / …" />
      </label>
      <label>
        <span>简介(255 字以内)</span>
        <input v-model="summary" type="text" maxlength="255" />
      </label>
      <label>
        <span>详细描述</span>
        <textarea v-model="description" rows="5" />
      </label>
      <p v-if="validationError" class="form-error">{{ validationError }}</p>
      <div class="form-actions">
        <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
        <button class="primary-btn" type="submit" :disabled="!canSubmit">
          {{ busy ? "保存中..." : "保存" }}
        </button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.scene-form { display: flex; flex-direction: column; gap: 14px; }
.scene-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.scene-form input, .scene-form textarea {
  padding: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}
.form-error { color: var(--danger); font-size: 12px; margin: 0; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
</style>
```

- [ ] **Step 2: typecheck + commit**

```bash
cd frontend && npm run typecheck
git add frontend/src/components/scene/SceneEditorModal.vue
git commit -m "feat(frontend): SceneEditorModal 场景编辑弹窗"
```

---

## Task 9: `CharacterAssetsPanel.vue` 升级 — 全面可交互

**Files:**
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`

交互点:

1. 顶部 `template #actions`:
   - 若 `stage_raw === "storyboard_ready"` 且 `characters.length === 0`:显示大按钮 "生成角色资产"(触发 `store.generateCharacters`)
   - 若主 job 运行中:显示 ProgressBar + "正在生成角色(x/y)"
   - 若失败:显示 banner + 重试按钮
   - demo 原 "新增角色资产" 按钮保持 `disabled` 占位(spec §7.3.3 明确不做手动新增)

2. 列表:每个 item 加 "主角 · 已锁定" 徽章 when `is_protagonist && locked`;单独 "已锁定" when `locked && !is_protagonist`

3. 详情区:
   - 参考图:`<img v-if="char.reference_image_url" :src="char.reference_image_url" loading="lazy" />` ;fallback 回原 `.silhouette` 占位
   - 按钮组:`编辑描述` / `重新生成参考图` / 未锁定时展示 `设为主角 · 锁定`;未锁定且非主角时额外展示 `仅锁定`;已锁定角色隐藏锁定按钮
   - regen 运行中:按钮替换成 "重生成中...(job <id 前 6>)",依据 `store.regenJobIdFor('character', id)`
   - 已锁定:按钮全部灰化,hover tip 指向 "回退阶段"

- [ ] **Step 1: 整体替换文件**

```vue
<!-- frontend/src/components/character/CharacterAssetsPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import CharacterEditorModal from "./CharacterEditorModal.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { confirm as uiConfirm } from "@/composables/useConfirm";
import { ApiError, messageFor } from "@/utils/error";
import type { CharacterAsset } from "@/types";
import type { CharacterUpdate, JobState } from "@/types/api";

const store = useWorkbenchStore();
const {
  current,
  selectedCharacter,
  selectedCharacterId,
  activeGenerateCharactersJobId,
  activeRegenJobEntries,
  generateCharactersError
} = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const editorOpen = ref(false);
const rollbackOpen = ref(false);
const busy = ref(false);
const starting = ref(false);

// ---- 生成主 job 轮询(空态入口) ----
const { job: generateJob } = useJobPolling(activeGenerateCharactersJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markGenerateCharactersSucceeded();
      toast.success("角色已生成");
    } catch (e) {
      store.markGenerateCharactersFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "生成失败");
    store.markGenerateCharactersFailed(msg);
    toast.error(msg);
  }
});

const generateProgressLabel = computed(() => {
  const j = generateJob.value;
  if (!j) return "正在排队…";
  if (j.total && j.total > 0) return `正在生成角色… ${j.done}/${j.total}`;
  return `正在生成角色… ${j.progress}%`;
});

// ---- 单项 regen 轮询(同一 panel 同时只允许一个 active regen) ----
const activeCharacterRegenJobId = computed(
  () => activeRegenJobEntries.value.find((e) => e.key.startsWith("character:"))?.jobId ?? null
);
const regenProgressByJobId = ref<Record<string, number>>({});
const selectedRegenProgress = computed(() =>
  activeCharacterRegenJobId.value ? regenProgressByJobId.value[activeCharacterRegenJobId.value] ?? 0 : 0
);

useJobPolling(
  activeCharacterRegenJobId,
  {
    onProgress: (job: JobState) => {
      regenProgressByJobId.value[job.id] = job.progress;
    },
    onSuccess: async () => {
      const entry = activeRegenJobEntries.value.find((e) => e.key.startsWith("character:"));
      if (entry) store.markRegenByKeySucceeded(entry.key);
      await store.reload();
      toast.success("角色参考图已重生成");
    },
    onError: (j, err) => {
      const entry = activeRegenJobEntries.value.find((e) => e.key.startsWith("character:"));
      if (entry) store.markRegenByKeyFailed(entry.key);
      const msg =
        j?.error_msg ??
        (err instanceof ApiError ? messageFor(err.code, err.message) : "重生成失败");
      toast.error(msg);
    }
  }
);

// ---- 触发动作 ----
async function handleGenerate() {
  if (!flags.value.canGenerateCharacters) {
    toast.warning("当前阶段不允许生成角色", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  starting.value = true;
  try {
    await store.generateCharacters({});
  } catch (e) {
    const msg = e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败";
    store.markGenerateCharactersFailed(msg);
    toast.error(msg);
  } finally {
    starting.value = false;
  }
}

function openEdit() {
  if (!flags.value.canEditCharacters) {
    toast.warning("当前阶段已锁定,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  editorOpen.value = true;
}

async function handleEditSubmit(payload: CharacterUpdate) {
  if (!selectedCharacter.value) return;
  busy.value = true;
  try {
    await store.patchCharacter(selectedCharacter.value.id, payload);
    toast.success("角色已保存");
    editorOpen.value = false;
  } catch (e) {
    if (e instanceof ApiError && e.code === 40301) {
      toast.warning("当前阶段已锁定,如需修改请回退阶段", {
        action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
      });
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("保存失败");
    }
  } finally {
    busy.value = false;
  }
}

async function handleRegen() {
  if (!selectedCharacter.value) return;
  if (!flags.value.canEditCharacters) {
    toast.warning("当前阶段已锁定,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  busy.value = true;
  try {
    await store.regenerateCharacter(selectedCharacter.value.id);
    toast.info("已触发重生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  } finally {
    busy.value = false;
  }
}

async function handleLock(asProtagonist: boolean) {
  if (!selectedCharacter.value) return;
  if (!flags.value.canLockCharacter) {
    toast.warning("当前阶段不允许锁定角色", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  const label = asProtagonist ? "设为主角并锁定" : "锁定角色";
  const body = asProtagonist
    ? "将此角色设为主角并入人像库。同一项目内只能有一个主角,已有的主角会自动降级为配角。此操作需调用人像库,约 10-120 秒。"
    : "锁定此角色,锁定后描述不可编辑,需先回退阶段。";
  const ok = await uiConfirm({ title: label, body, confirmText: "确认", danger: false });
  if (!ok) return;
  busy.value = true;
  const waitingToastId = asProtagonist
    ? toast.info("正在调用人像库,通常 30-90 秒", {
        detail: "请保持当前页面,完成后会自动刷新状态。",
        persist: true
      })
    : null;
  try {
    await store.lockCharacter(selectedCharacter.value.id, { as_protagonist: asProtagonist });
    toast.success(asProtagonist ? "主角已锁定并入库" : "角色已锁定");
  } catch (e) {
    if (e instanceof ApiError && e.code === 42201) {
      toast.error(messageFor(42201, e.message));
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("锁定失败");
    }
  } finally {
    if (waitingToastId !== null) toast.dismiss(waitingToastId);
    busy.value = false;
  }
}

// ---- UI helpers ----
function badgeFor(c: CharacterAsset): string | null {
  if (c.is_protagonist && c.locked) return "主角 · 已锁定";
  if (c.locked) return "已锁定";
  if (c.is_protagonist) return "主角";
  return null;
}

const canStartGenerate = computed(
  () =>
    flags.value.canGenerateCharacters &&
    (current.value?.characters.length ?? 0) === 0 &&
    !activeGenerateCharactersJobId.value
);

const selectedIsLocked = computed(() => !!selectedCharacter.value?.locked);
const selectedIsProtagonist = computed(() => !!selectedCharacter.value?.is_protagonist);
const selectedHasRegenJob = computed(() =>
  activeRegenJobEntries.value.some((e) => e.key.startsWith("character:"))
);
</script>

<template>
  <PanelSection v-if="current" kicker="03" title="角色设定">
    <template #actions>
      <button class="ghost-btn" type="button" disabled>新增角色资产</button>
    </template>

    <!-- 生成主 job 进度 -->
    <div v-if="activeGenerateCharactersJobId" class="gen-banner running">
      <div class="gen-head">
        <strong>{{ generateProgressLabel }}</strong>
      </div>
      <ProgressBar :value="generateJob?.progress ?? 0" />
    </div>

    <!-- 生成失败 banner -->
    <div v-else-if="generateCharactersError" class="gen-banner error">
      <div class="gen-head">
        <strong>角色生成失败</strong>
        <button class="ghost-btn small" @click="handleGenerate">重试</button>
      </div>
      <p>{{ generateCharactersError }}</p>
    </div>

    <!-- 空态大按钮 -->
    <div v-else-if="canStartGenerate" class="empty-cta">
      <p>尚未生成角色 · 基于已确认分镜抽取项目中的角色并生成参考图</p>
      <button class="primary-btn large" :disabled="starting" @click="handleGenerate">
        {{ starting ? "启动中..." : "生成角色资产" }}
      </button>
    </div>
    <div v-else-if="!current.characters.length" class="empty-note">
      尚未生成角色 · 分镜生成并确认后可触发 AI 抽取
    </div>

    <!-- 列表 + 详情 -->
    <div v-if="current.characters.length" class="asset-browser">
      <div class="asset-list-panel">
        <div class="list-head">
          <strong>所有角色</strong>
          <span>{{ current.characters.length }} 个资产</span>
        </div>
        <div class="asset-list">
          <button
            v-for="character in current.characters"
            :key="character.id"
            class="asset-list-item"
            :class="{ active: selectedCharacterId === character.id }"
            type="button"
            @click="store.selectCharacter(character.id)"
          >
            <div class="list-item-head">
              <strong>{{ character.name }}</strong>
              <span v-if="badgeFor(character)" class="badge">{{ badgeFor(character) }}</span>
            </div>
            <small>{{ character.summary }}</small>
          </button>
        </div>
      </div>

      <div v-if="selectedCharacter" class="asset-detail-panel">
        <div class="subpage-head">
          <div>
            <p class="panel-kicker">角色详情</p>
            <h3>{{ selectedCharacter.name }}</h3>
          </div>
          <span class="tag accent">{{ selectedCharacter.role }}</span>
        </div>

        <div class="asset-layout">
          <div class="reference-stage character-stage">
            <div class="reference-badge">角色参考图</div>
            <img
              v-if="selectedCharacter.reference_image_url"
              :src="selectedCharacter.reference_image_url"
              :alt="selectedCharacter.name"
              loading="lazy"
              class="ref-image"
            />
            <div v-else class="silhouette"></div>
          </div>

          <div class="asset-info">
            <article class="asset-copy">
              <label>角色描述</label>
              <p>{{ selectedCharacter.description || "(尚无描述)" }}</p>
            </article>

            <article class="asset-meta">
              <span>视频形象参考</span>
              <ul v-if="selectedCharacter.meta.length">
                <li v-for="meta in selectedCharacter.meta" :key="meta">{{ meta }}</li>
              </ul>
              <p v-else class="faint">暂无 meta</p>
            </article>

            <div class="asset-actions">
              <button
                class="ghost-btn"
                :disabled="busy || selectedIsLocked || !flags.canEditCharacters"
                :title="selectedIsLocked || !flags.canEditCharacters ? '已锁定,如需修改请回退阶段' : '编辑描述'"
                @click="openEdit"
              >
                编辑描述
              </button>
              <button
                class="ghost-btn"
                :disabled="busy || selectedIsLocked || selectedHasRegenJob || !flags.canEditCharacters"
                :title="selectedIsLocked || !flags.canEditCharacters ? '已锁定,如需修改请回退阶段' : '重新生成参考图'"
                @click="handleRegen"
              >
                {{ selectedHasRegenJob ? `重生成中…(${selectedRegenProgress}%)` : "重新生成参考图" }}
              </button>
              <button
                v-if="!selectedIsLocked"
                class="primary-btn"
                :disabled="busy || !flags.canLockCharacter"
                :title="flags.canLockCharacter ? '设为主角并锁定' : '当前阶段不允许锁定角色,请回退阶段'"
                @click="handleLock(true)"
              >
                设为主角 · 锁定
              </button>
              <button
                v-if="!selectedIsLocked && !selectedIsProtagonist"
                class="ghost-btn"
                :disabled="busy || !flags.canLockCharacter"
                :title="flags.canLockCharacter ? '仅锁定角色' : '当前阶段不允许锁定角色,请回退阶段'"
                @click="handleLock(false)"
              >
                仅锁定
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <CharacterEditorModal
      :open="editorOpen"
      :character="selectedCharacter"
      :busy="busy"
      @close="editorOpen = false"
      @submit="handleEditSubmit"
    />

    <StageRollbackModal :open="rollbackOpen" @close="rollbackOpen = false" />
  </PanelSection>
</template>

<style scoped>
/* 保留 M2 / demo 的既有样式,下列为新增 */
.gen-banner {
  margin-bottom: 16px;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--panel-border);
  background: rgba(255,255,255,0.03);
}
.gen-banner.error { border-color: var(--danger); }
.gen-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.empty-cta { text-align: center; padding: 32px 0 16px; }
.empty-cta p { color: var(--text-faint); margin-bottom: 16px; }
.list-item-head { display: flex; justify-content: space-between; align-items: center; }
.badge {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: var(--accent-dim); color: var(--accent);
}
.ref-image {
  position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
}
.asset-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.faint { color: var(--text-faint); font-size: 12px; }
/* 其余已有样式略 — 从 M2 文件保留到这里 */

.asset-browser { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 20px; }
.asset-list-panel { padding: 18px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: var(--radius-md); }
.list-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.list-head strong { font-size: 15px; }
.list-head span { font-size: 12px; color: var(--text-faint); }
.asset-list { display: flex; flex-direction: column; gap: 10px; }
.asset-list-item { width: 100%; padding: 14px; text-align: left; background: rgba(255,255,255,0.02); border: 1px solid var(--panel-border); border-radius: var(--radius-sm); cursor: pointer; transition: all 160ms; }
.asset-list-item:hover { background: rgba(255,255,255,0.05); }
.asset-list-item.active { background: var(--accent-dim); border-color: var(--accent); }
.asset-list-item strong { display: block; font-size: 14px; margin-bottom: 4px; }
.asset-list-item small { display: block; font-size: 12px; color: var(--text-muted); }
.asset-detail-panel { padding: 24px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: var(--radius-md); }
.subpage-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.subpage-head h3 { margin: 0; font-size: 22px; }
.asset-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 24px; }
.reference-stage { position: relative; min-height: 280px; border-radius: var(--radius-md); background: #0b0d1a; border: 1px solid var(--panel-border); overflow: hidden; }
.reference-badge { position: absolute; top: 12px; left: 12px; padding: 4px 8px; background: rgba(0,0,0,0.5); color: #fff; font-size: 10px; border-radius: 4px; z-index: 1; }
.silhouette { position: absolute; bottom: 0; left: 50%; transform: translateX(-50%); width: 120px; height: 200px; background: linear-gradient(180deg, #333, #111); border-radius: 60px 60px 0 0; }
.asset-info { display: flex; flex-direction: column; gap: 20px; }
.asset-copy label { display: block; font-size: 12px; color: var(--accent); margin-bottom: 8px; }
.asset-copy p { margin: 0; font-size: 14px; color: var(--text-muted); line-height: 1.6; }
.asset-meta span { display: block; font-size: 12px; color: var(--text-faint); margin-bottom: 10px; }
.asset-meta ul { margin: 0; padding-left: 18px; font-size: 13px; color: var(--text-muted); line-height: 1.6; }
.tag.accent { background: var(--accent-dim); color: var(--accent); padding: 4px 10px; border-radius: 999px; font-size: 12px; }
.empty-note { padding: 40px 0; text-align: center; color: var(--text-faint); font-size: 14px; }
</style>
```

- [ ] **Step 2: typecheck + 手工冒烟(后端 mock 下)**

```bash
cd frontend && npm run typecheck
# 手工:
# 1) 建项目 → parse → confirm → stage=storyboard_ready
# 2) 进入角色 Panel,点"生成角色资产",ProgressBar 推进 → 列表出现 3 个角色
# 3) 选中一个,点"设为主角 · 锁定" → toast "主角已锁定" → 列表徽章 "主角·已锁定"
# 4) stage_raw 应变为 characters_locked(页面顶栏),角色"编辑描述"按钮灰化
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/character/CharacterAssetsPanel.vue
git commit -m "feat(frontend): CharacterAssetsPanel 全面可交互(生成/编辑/重生成/锁定)"
```

---

## Task 10: `SceneAssetsPanel.vue` 升级 — 含 bind_scene

**Files:**
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`

交互点:

1. 顶部:与 CharacterAssetsPanel 对称 — 空态大按钮 / 主 job 进度 / 失败 banner
2. 列表:`scene.locked` → "已锁定" 徽章;`scene.usage` 继续显示
3. 详情区:
   - 参考图:实图替换,fallback 回原 `theme-palace/academy/harbor` 装饰层
   - 按钮组:`编辑描述` / `重新生成参考图` / `绑定当前镜头到此场景` / `锁定场景`
4. "绑定当前镜头到此场景":使用 `useWorkbenchStore().currentShot`(分镜 panel 选中的 shot),调用 `store.bindShotScene(currentShot.id, selectedScene.id)`;若未选中 shot → toast "请先在分镜 Panel 选中一个镜头"

- [ ] **Step 1: 整体替换文件**

```vue
<!-- frontend/src/components/scene/SceneAssetsPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import SceneEditorModal from "./SceneEditorModal.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { confirm as uiConfirm } from "@/composables/useConfirm";
import { ApiError, messageFor } from "@/utils/error";
import type { SceneAsset } from "@/types";
import type { JobState, SceneUpdate } from "@/types/api";

const store = useWorkbenchStore();
const {
  current,
  selectedScene,
  selectedSceneId,
  currentShot,
  activeGenerateScenesJobId,
  activeRegenJobEntries,
  generateScenesError
} = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const editorOpen = ref(false);
const rollbackOpen = ref(false);
const busy = ref(false);
const starting = ref(false);

// ---- 主 job 轮询 ----
const { job: generateJob } = useJobPolling(activeGenerateScenesJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markGenerateScenesSucceeded();
      toast.success("场景已生成");
    } catch (e) {
      store.markGenerateScenesFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "生成失败");
    store.markGenerateScenesFailed(msg);
    toast.error(msg);
  }
});

const generateProgressLabel = computed(() => {
  const j = generateJob.value;
  if (!j) return "正在排队…";
  if (j.total && j.total > 0) return `正在生成场景… ${j.done}/${j.total}`;
  return `正在生成场景… ${j.progress}%`;
});

// ---- 单项 regen 轮询(同一 panel 同时只允许一个 active regen) ----
const activeSceneRegenJobId = computed(
  () => activeRegenJobEntries.value.find((e) => e.key.startsWith("scene:"))?.jobId ?? null
);
const regenProgressByJobId = ref<Record<string, number>>({});
const selectedRegenProgress = computed(() =>
  activeSceneRegenJobId.value ? regenProgressByJobId.value[activeSceneRegenJobId.value] ?? 0 : 0
);

useJobPolling(
  activeSceneRegenJobId,
  {
    onProgress: (job: JobState) => {
      regenProgressByJobId.value[job.id] = job.progress;
    },
    onSuccess: async () => {
      const entry = activeRegenJobEntries.value.find((e) => e.key.startsWith("scene:"));
      if (entry) store.markRegenByKeySucceeded(entry.key);
      await store.reload();
      toast.success("场景参考图已重生成");
    },
    onError: (j, err) => {
      const entry = activeRegenJobEntries.value.find((e) => e.key.startsWith("scene:"));
      if (entry) store.markRegenByKeyFailed(entry.key);
      toast.error(j?.error_msg ?? (err instanceof ApiError ? messageFor(err.code, err.message) : "重生成失败"));
    }
  }
);

// ---- 动作 ----
async function handleGenerate() {
  if (!flags.value.canGenerateScenes) {
    toast.warning("当前阶段不允许生成场景", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  starting.value = true;
  try {
    await store.generateScenes({});
  } catch (e) {
    const msg = e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败";
    store.markGenerateScenesFailed(msg);
    toast.error(msg);
  } finally {
    starting.value = false;
  }
}

function openEdit() {
  if (!flags.value.canEditScenes) {
    toast.warning("当前阶段已锁定,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  editorOpen.value = true;
}

async function handleEditSubmit(payload: SceneUpdate) {
  if (!selectedScene.value) return;
  busy.value = true;
  try {
    await store.patchScene(selectedScene.value.id, payload);
    toast.success("场景已保存");
    editorOpen.value = false;
  } catch (e) {
    if (e instanceof ApiError && e.code === 40301) {
      toast.warning("当前阶段已锁定,如需修改请回退阶段", {
        action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
      });
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("保存失败");
    }
  } finally {
    busy.value = false;
  }
}

async function handleRegen() {
  if (!selectedScene.value) return;
  if (!flags.value.canEditScenes) {
    toast.warning("当前阶段已锁定,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  busy.value = true;
  try {
    await store.regenerateScene(selectedScene.value.id);
    toast.info("已触发重生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  } finally {
    busy.value = false;
  }
}

async function handleBind() {
  if (!selectedScene.value) return;
  const shot = currentShot.value;
  if (!shot) {
    toast.warning("请先在分镜 Panel 选中一个镜头");
    return;
  }
  if (!flags.value.canBindScene) {
    toast.warning("当前阶段不允许绑定场景", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  busy.value = true;
  try {
    await store.bindShotScene(shot.id, selectedScene.value.id);
    toast.success(`镜头 ${String(shot.idx).padStart(2, "0")} 已绑定到「${selectedScene.value.name}」`);
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "绑定失败");
  } finally {
    busy.value = false;
  }
}

async function handleLock() {
  if (!selectedScene.value) return;
  if (!flags.value.canLockScene) {
    toast.warning("当前阶段不允许锁定场景", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  const ok = await uiConfirm({
    title: "锁定场景",
    body: "锁定后描述不可编辑;当项目内所有镜头均已绑定到已锁定场景时,项目会进入 scenes_locked 阶段。",
    confirmText: "确认锁定",
    danger: false
  });
  if (!ok) return;
  busy.value = true;
  try {
    await store.lockScene(selectedScene.value.id);
    toast.success("场景已锁定");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "锁定失败");
  } finally {
    busy.value = false;
  }
}

// ---- UI helpers ----
const canStartGenerate = computed(
  () =>
    flags.value.canGenerateScenes &&
    (current.value?.scenes.length ?? 0) === 0 &&
    !activeGenerateScenesJobId.value
);
const THEME_CLASS: Record<string, string> = {
  palace: "theme-palace",
  academy: "theme-academy",
  harbor: "theme-harbor"
};
const themeClass = (s: SceneAsset) => (s.theme ? THEME_CLASS[s.theme] ?? "" : "");
const selectedIsLocked = computed(() => !!selectedScene.value?.locked);
const selectedHasRegenJob = computed(() =>
  activeRegenJobEntries.value.some((e) => e.key.startsWith("scene:"))
);
</script>

<template>
  <PanelSection v-if="current" kicker="04" title="场景设定">
    <template #actions>
      <button class="ghost-btn" type="button" disabled>新增场景资产</button>
    </template>

    <div v-if="activeGenerateScenesJobId" class="gen-banner running">
      <div class="gen-head">
        <strong>{{ generateProgressLabel }}</strong>
      </div>
      <ProgressBar :value="generateJob?.progress ?? 0" />
    </div>

    <div v-else-if="generateScenesError" class="gen-banner error">
      <div class="gen-head">
        <strong>场景生成失败</strong>
        <button class="ghost-btn small" @click="handleGenerate">重试</button>
      </div>
      <p>{{ generateScenesError }}</p>
    </div>

    <div v-else-if="canStartGenerate" class="empty-cta">
      <p>尚未生成场景 · 主角锁定后可触发 AI 匹配项目中需要的场景</p>
      <button class="primary-btn large" :disabled="starting" @click="handleGenerate">
        {{ starting ? "启动中..." : "生成场景资产" }}
      </button>
    </div>
    <div v-else-if="!current.scenes.length" class="empty-note">
      尚未生成场景 · 角色锁定后将自动匹配场景
    </div>

    <div v-if="current.scenes.length" class="asset-browser">
      <div class="asset-list-panel">
        <div class="list-head">
          <strong>所有场景</strong>
          <span>{{ current.scenes.length }} 个资产</span>
        </div>
        <div class="asset-list">
          <button
            v-for="scene in current.scenes"
            :key="scene.id"
            class="asset-list-item"
            :class="{ active: selectedSceneId === scene.id }"
            type="button"
            @click="store.selectScene(scene.id)"
          >
            <div class="list-item-head">
              <strong>{{ scene.name }}</strong>
              <span v-if="scene.locked" class="badge">已锁定</span>
            </div>
            <small>{{ scene.summary }}</small>
          </button>
        </div>
      </div>

      <div v-if="selectedScene" class="asset-detail-panel">
        <div class="subpage-head">
          <div>
            <p class="panel-kicker">场景详情</p>
            <h3>{{ selectedScene.name }}</h3>
          </div>
          <span class="tag">{{ selectedScene.usage }}</span>
        </div>

        <div class="asset-layout">
          <div class="reference-stage scene-stage" :class="themeClass(selectedScene)">
            <div class="reference-badge">场景参考图</div>
            <img
              v-if="selectedScene.reference_image_url"
              :src="selectedScene.reference_image_url"
              :alt="selectedScene.name"
              loading="lazy"
              class="ref-image"
            />
            <div v-else class="scene-layers">
              <span class="moon" />
              <span class="wall" />
              <span class="well" />
            </div>
          </div>

          <div class="asset-info">
            <article class="asset-copy">
              <label>场景描述</label>
              <p>{{ selectedScene.description || "(尚无描述)" }}</p>
            </article>

            <article class="asset-meta">
              <span>视觉风格参考</span>
              <ul v-if="selectedScene.meta.length">
                <li v-for="meta in selectedScene.meta" :key="meta">{{ meta }}</li>
              </ul>
              <p v-else class="faint">暂无 meta</p>
            </article>

            <div class="asset-actions">
              <button
                class="ghost-btn"
                :disabled="busy || selectedIsLocked || !flags.canEditScenes"
                :title="selectedIsLocked || !flags.canEditScenes ? '已锁定,如需修改请回退阶段' : '编辑描述'"
                @click="openEdit"
              >
                编辑描述
              </button>
              <button
                class="ghost-btn"
                :disabled="busy || selectedIsLocked || selectedHasRegenJob || !flags.canEditScenes"
                :title="selectedIsLocked || !flags.canEditScenes ? '已锁定,如需修改请回退阶段' : '重新生成参考图'"
                @click="handleRegen"
              >
                {{ selectedHasRegenJob ? `重生成中…(${selectedRegenProgress}%)` : "重新生成参考图" }}
              </button>
              <button
                class="ghost-btn"
                :disabled="busy || !flags.canBindScene"
                :title="flags.canBindScene ? '绑定当前选中镜头到此场景' : '当前阶段不允许绑定场景,请回退阶段'"
                @click="handleBind"
              >
                {{
                  currentShot
                    ? `绑定镜头 ${String(currentShot.idx).padStart(2, "0")} → 此场景`
                    : "绑定当前选中镜头"
                }}
              </button>
              <button
                v-if="!selectedIsLocked"
                class="primary-btn"
                :disabled="busy || !flags.canLockScene"
                :title="flags.canLockScene ? '锁定场景' : '当前阶段不允许锁定场景,请回退阶段'"
                @click="handleLock"
              >
                锁定场景
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <SceneEditorModal
      :open="editorOpen"
      :scene="selectedScene"
      :busy="busy"
      @close="editorOpen = false"
      @submit="handleEditSubmit"
    />

    <StageRollbackModal :open="rollbackOpen" @close="rollbackOpen = false" />
  </PanelSection>
</template>

<style scoped>
/* 保留 demo 既有样式,以下为新增 */
.gen-banner { margin-bottom: 16px; padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--panel-border); background: rgba(255,255,255,0.03); }
.gen-banner.error { border-color: var(--danger); }
.gen-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.empty-cta { text-align: center; padding: 32px 0 16px; }
.empty-cta p { color: var(--text-faint); margin-bottom: 16px; }
.list-item-head { display: flex; justify-content: space-between; align-items: center; }
.badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); color: var(--text-muted); }
.ref-image { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.asset-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.faint { color: var(--text-faint); font-size: 12px; }
/* 以下从 M2 SceneAssetsPanel.vue 保留 */
.asset-browser { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 20px; }
.asset-list-panel { padding: 18px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: var(--radius-md); }
.list-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.list-head strong { font-size: 15px; }
.list-head span { font-size: 12px; color: var(--text-faint); }
.asset-list { display: flex; flex-direction: column; gap: 10px; }
.asset-list-item { width: 100%; padding: 14px; text-align: left; background: rgba(255,255,255,0.02); border: 1px solid var(--panel-border); border-radius: var(--radius-sm); cursor: pointer; transition: all 160ms; }
.asset-list-item:hover { background: rgba(255,255,255,0.05); }
.asset-list-item.active { background: var(--accent-dim); border-color: var(--accent); }
.asset-list-item strong { display: block; font-size: 14px; margin-bottom: 4px; }
.asset-list-item small { display: block; font-size: 12px; color: var(--text-muted); }
.asset-detail-panel { padding: 24px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: var(--radius-md); }
.subpage-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.subpage-head h3 { margin: 0; font-size: 22px; }
.asset-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 24px; }
.reference-stage { position: relative; min-height: 280px; border-radius: var(--radius-md); background: #0b0d1a; border: 1px solid var(--panel-border); overflow: hidden; }
.reference-badge { position: absolute; top: 12px; left: 12px; padding: 4px 8px; background: rgba(0,0,0,0.5); color: #fff; font-size: 10px; border-radius: 4px; z-index: 1; }
.scene-layers { position: absolute; inset: 0; }
.moon { position: absolute; top: 40px; right: 40px; width: 60px; height: 60px; background: radial-gradient(circle, #fff, transparent); border-radius: 50%; opacity: 0.8; }
.wall { position: absolute; bottom: 40px; left: 20px; right: 20px; height: 100px; background: rgba(255,255,255,0.1); border-radius: 12px; }
.well { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); width: 80px; height: 40px; background: rgba(255,255,255,0.05); border: 4px solid rgba(255,255,255,0.1); border-radius: 40px 40px 0 0; }
.asset-info { display: flex; flex-direction: column; gap: 20px; }
.asset-copy label { display: block; font-size: 12px; color: var(--accent); margin-bottom: 8px; }
.asset-copy p { margin: 0; font-size: 14px; color: var(--text-muted); line-height: 1.6; }
.asset-meta span { display: block; font-size: 12px; color: var(--text-faint); margin-bottom: 10px; }
.asset-meta ul { margin: 0; padding-left: 18px; font-size: 13px; color: var(--text-muted); line-height: 1.6; }
.tag { background: rgba(255,255,255,0.05); color: var(--text-muted); padding: 4px 10px; border-radius: 999px; font-size: 12px; }
.empty-note { padding: 40px 0; text-align: center; color: var(--text-faint); font-size: 14px; }
</style>
```

- [ ] **Step 2: typecheck + 手工冒烟**

```bash
cd frontend && npm run typecheck
# 在 stage_raw=characters_locked 下:点生成 → 轮询 → 出列表 → 选一个 scene → 点"绑定镜头 XX → 此场景" → "锁定场景"
# 绑定所有镜头到同一场景 + 只锁定该场景 后 reload,页面顶栏 stage 应变为 "场景已匹配"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/scene/SceneAssetsPanel.vue
git commit -m "feat(frontend): SceneAssetsPanel 全面可交互(生成/编辑/重生成/绑定/锁定)"
```

---

## Task 11: `scripts/smoke_m3a.sh` 全链路冒烟

**Files:**
- Create: `frontend/scripts/smoke_m3a.sh`

- [ ] **Step 1: 实现**

```bash
#!/usr/bin/env bash
# frontend/scripts/smoke_m3a.sh
# 前置:后端已在 127.0.0.1:8000 启动(AI_PROVIDER_MODE=mock + CELERY_TASK_ALWAYS_EAGER=true)
# 本脚本只打 API,不启动浏览器,验证前端依赖的后端 M3a 端点真实可用

set -euo pipefail

API="${API:-http://127.0.0.1:8000/api/v1}"
TS=$(date +%s)
NAME="m3a-fe-smoke-$TS"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "缺少 $1,请先安装" >&2; exit 2; }
}
require curl
require jq

echo "[1/9] 创建项目 $NAME"
pid=$(curl -s -X POST "$API/projects" -H "Content-Type: application/json" \
  -d "$(jq -n --arg name "$NAME" '{name:$name, story:"古风权谋,皇权更迭,秦昭与江离,少年天子与摄政王的暗流。",genre:"古风权谋",ratio:"9:16"}')" \
  | jq -r '.data.id')
echo "  project id: $pid"

echo "[2/9] 触发 parse"
jid=$(curl -s -X POST "$API/projects/$pid/parse" | jq -r '.data.job_id')
echo "  job: $jid"

echo "[3/9] 等 parse 完成"
for i in {1..30}; do
  st=$(curl -s "$API/jobs/$jid" | jq -r '.data.status')
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "parse 失败"; exit 1; }
  sleep 1
done
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
echo "  stage_raw=$stage_raw"
[ "$stage_raw" = "storyboard_ready" ] || { echo "期望 storyboard_ready"; exit 1; }

echo "[4/9] 确认分镜"
curl -s -X POST "$API/projects/$pid/storyboards/confirm" >/dev/null
# mock 下 confirm 不改 stage;stage_raw 仍是 storyboard_ready(见 backend M2 plan)

echo "[5/9] 生成角色"
ack=$(curl -s -X POST "$API/projects/$pid/characters/generate" -H "Content-Type: application/json" -d '{}')
gjid=$(echo "$ack" | jq -r '.data.job_id')
echo "  generate job: $gjid"
for i in {1..60}; do
  st=$(curl -s "$API/jobs/$gjid" | jq -r '.data.status')
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "generate_characters 失败"; exit 1; }
  sleep 1
done
chars=$(curl -s "$API/projects/$pid" | jq '.data.characters | length')
[ "$chars" -gt 0 ] || { echo "角色未落库"; exit 1; }
echo "  characters=$chars"

echo "[6/9] 锁定主角"
cid=$(curl -s "$API/projects/$pid" | jq -r '.data.characters[0].id')
curl -s -X POST "$API/projects/$pid/characters/$cid/lock" \
  -H "Content-Type: application/json" -d '{"as_protagonist": true}' >/dev/null
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
[ "$stage_raw" = "characters_locked" ] || { echo "期望 characters_locked 实际 $stage_raw"; exit 1; }
echo "  stage_raw=$stage_raw"

echo "[7/9] 生成场景 + 轮询"
sack=$(curl -s -X POST "$API/projects/$pid/scenes/generate" -H "Content-Type: application/json" -d '{}')
sjid=$(echo "$sack" | jq -r '.data.job_id')
for i in {1..60}; do
  st=$(curl -s "$API/jobs/$sjid" | jq -r '.data.status')
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "generate_scenes 失败"; exit 1; }
  sleep 1
done
scenes=$(curl -s "$API/projects/$pid" | jq '.data.scenes | length')
[ "$scenes" -gt 0 ] || { echo "场景未落库"; exit 1; }
echo "  scenes=$scenes"

echo "[8/9] 绑定每个镜头到第一个场景 + 只锁定被绑定场景"
first_scene=$(curl -s "$API/projects/$pid" | jq -r '.data.scenes[0].id')
for sid in $(curl -s "$API/projects/$pid" | jq -r '.data.storyboards[].id'); do
  curl -s -X POST "$API/projects/$pid/storyboards/$sid/bind_scene" \
    -H "Content-Type: application/json" -d "$(jq -n --arg sc "$first_scene" '{scene_id:$sc}')" >/dev/null
done
curl -s -X POST "$API/projects/$pid/scenes/$first_scene/lock" \
  -H "Content-Type: application/json" -d '{}' >/dev/null

echo "[9/9] 校验 stage=scenes_locked"
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
[ "$stage_raw" = "scenes_locked" ] || { echo "期望 scenes_locked 实际 $stage_raw"; exit 1; }
echo "SMOKE M3A OK — project=$pid stage=$stage_raw"
```

- [ ] **Step 2: chmod + 手动跑一次**

```bash
chmod +x frontend/scripts/smoke_m3a.sh
# 后端必须先启动
./frontend/scripts/smoke_m3a.sh
```

Expected: 最后一行 `SMOKE M3A OK — project=<ulid> stage=scenes_locked`。

- [ ] **Step 3: Commit**

```bash
git add frontend/scripts/smoke_m3a.sh
git commit -m "test(frontend): M3a 全链路冒烟脚本"
```

---

## Task 12: README 更新 + DoD

**Files:**
- Modify: `frontend/README.md`

- [ ] **Step 1: 在 `## M2 范围` 之后追加 `## M3a 范围`**

```markdown
## M3a 范围

M3a 在 M2 的分镜闭环之上,打通了"生成角色 → 锁定主角 → 生成场景 → 绑定镜头 → 锁定场景"的资产链路。

### 新增端点对接

| 端点 | 组件 / Store |
| --- | --- |
| `GET /api/v1/projects/{id}/characters` | 调试/备用端点;页面读路径仍走聚合 `GET /projects/{id}` |
| `POST /api/v1/projects/{id}/characters/generate` | `CharacterAssetsPanel`(空态大按钮)+ `store.generateCharacters` |
| `PATCH /api/v1/projects/{id}/characters/{cid}` | `CharacterEditorModal` + `store.patchCharacter` |
| `POST /api/v1/projects/{id}/characters/{cid}/regenerate` | `CharacterAssetsPanel` "重新生成参考图" |
| `POST /api/v1/projects/{id}/characters/{cid}/lock` | `CharacterAssetsPanel` "设为主角 · 锁定" / "仅锁定" |
| `POST /api/v1/projects/{id}/scenes/generate` | `SceneAssetsPanel`(空态大按钮) |
| `PATCH /api/v1/projects/{id}/scenes/{sid}` | `SceneEditorModal` |
| `POST /api/v1/projects/{id}/scenes/{sid}/regenerate` | `SceneAssetsPanel` "重新生成参考图" |
| `POST /api/v1/projects/{id}/scenes/{sid}/lock` | `SceneAssetsPanel` "锁定场景" |
| `POST /api/v1/projects/{id}/storyboards/{shot_id}/bind_scene` | `SceneAssetsPanel` "绑定当前选中镜头" |

### 阶段门

| 操作 | 允许的 `stage_raw` |
| --- | --- |
| 生成/编辑/锁定角色 | `storyboard_ready` |
| 生成/编辑/绑定/锁定场景 | `characters_locked` |

所有被阶段门拦截的写按钮会 toast + 弹 `StageRollbackModal`。

`StageRollbackModal` 必须保持 prop-controlled(`:open` + `@close`),可在 Character/Scene 两个 panel 各挂一个实例;不要改成全局单例弹窗。

### 已知后端保留字段

`CharacterGenerateRequest.extra_hints` 与 `SceneGenerateRequest.template_whitelist` 本期只保留 schema 与请求透传,后端 M3a 暂不消费它们来改写 prompt 或筛选模板。UI 不应承诺这些输入会影响 AI 结果;后续 M3b 再补后端消费逻辑。

### 新增错误码映射

| code | 文案 |
| --- | --- |
| 42201 | AI 内容违规,请修改文案后重试 |

### 本地联调

```bash
# 1) 后端(mock + EAGER)
cd backend && AI_PROVIDER_MODE=mock CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload

# 2) 前端
cd frontend && npm run dev

# 3) 冒烟
./frontend/scripts/smoke_m3a.sh
```

### M3a 不包含

- 镜头渲染、render 版本历史(M3b/c)
- 导出(M4)
- 手动新增角色 / 场景(后端无对应 POST 端点,demo 占位按钮保持 disabled)
- 分镜拖拽绑定场景(用"当前选中镜头 → 此场景"按钮;拖拽 M3b+)
- 主角人像库专用进度条(通过 `meta` 里的 "人像库:Active" 文本体现)
- extra_hints / template_whitelist 对 AI 结果的实际影响(后端 M3a 暂不消费)
```

- [ ] **Step 2: 跑完整自检**

```bash
cd frontend
npm run typecheck
npm test
npm run build
# 后端启动后:
./frontend/scripts/smoke_m3a.sh
```

Expected 全部绿。

- [ ] **Step 3: Commit**

```bash
git add frontend/README.md
git commit -m "docs(frontend): M3a 范围 / 端点 / 阶段门速览"
```

---

## DoD

- [ ] Task 0 合入后端(aggregate 包含 `is_protagonist`/`locked`/`meta` 人像库状态/storyboard 时间字段;`bind_scene` 用 JSON body + 返回 `scene_name`;generate/lock 阶段错误码统一 40301;`role` 中文映射修复)。校验门:
  - [ ] `cd backend && ./.venv/bin/pytest tests/integration/test_projects_api.py tests/integration/test_bind_scene.py -v` 全绿(覆盖 Step 7 三条契约测试 `test_aggregate_includes_lock_flags` / `test_bind_scene_uses_json_body_and_returns_scene_name` / `test_bind_scene_rejects_wrong_stage_with_40301`)
  - [ ] `curl /projects/<id> | jq '.data.characters[0]'` 可见 `is_protagonist` / `locked` / `meta:["人像库:Active"]`
  - [ ] `curl /projects/<id> | jq '.data.storyboards[0]'` 可见 `current_render_id` / `created_at` / `updated_at`
  - [ ] `curl -X POST /storyboards/<shot_id>/bind_scene -d '{"scene_id":"..."}'` 返回 `{shot_id, scene_id, scene_name}`,错误阶段返回 HTTP 403 + envelope `40301`
- [ ] `npm run typecheck` 无新增 error
- [ ] `npm test` 全绿,覆盖新增的 api client + workbench 写动作 + 42201 错误码映射 + useStageGate M3a flag
- [ ] `npm run build` 成功,`dist/` 产物 gzipped < 500 KB(M2 约 180 KB,M3a 追加代码不应超 50 KB gzip)
- [ ] `./frontend/scripts/smoke_m3a.sh` 全绿(mock 后端下)
- [ ] 手工浏览器回归(dev server + mock 后端):
  - [ ] 建项目 → parse → confirm(stage=storyboard_ready)
  - [ ] 角色 Panel 空态 → 生成 → ProgressBar 推进 → 列表渲染
  - [ ] 选中角色 → 编辑描述(弹窗 → 保存 → toast)
  - [ ] "设为主角 · 锁定" → toast "主角已锁定" → 列表徽章 → 顶栏 stage=角色已锁定
  - [ ] 角色 Panel 所有写按钮在 stage=角色已锁定 下均灰化,hover 指向回退
  - [ ] 场景 Panel 空态 → 生成 → 列表渲染
  - [ ] 选中场景 → "绑定镜头 XX → 此场景"(依赖分镜 Panel 选中 shot)→ reload 看到 usage 加一
  - [ ] 所有镜头绑定到同一场景 + 只锁定被绑定场景后 → stage=场景已匹配
- [ ] 错误码 42201 回归:在后端手工触发 mock `VolcanoContentFilterError` 路径(或单独单测)确认前端 toast 文案为 "AI 内容违规,请修改文案后重试"
- [ ] 前后端契约复核:`curl $API/projects/<id> | jq '.data.characters[0], .data.scenes[0]' ` 字段名与 `frontend/src/types/index.ts` 的 `CharacterAsset` / `SceneAsset` 一一对应(is_protagonist / locked / reference_image_url 齐全)

---

## 附录 A:任务依赖图

```
Task 0 (后端契约)
  └─→ Task 1 (types)
        ├─→ Task 2 (characters api)
        │     └─→ Task 6 (store)
        ├─→ Task 3 (scenes api)
        │     └─→ Task 6
        ├─→ Task 4 (useStageGate)
        │     └─→ Task 9/10 (panels)
        └─→ Task 5 (error 42201)
              └─→ Task 9/10
Task 6 (store)
  ├─→ Task 7 (CharacterEditorModal)
  ├─→ Task 8 (SceneEditorModal)
  ├─→ Task 9 (CharacterAssetsPanel)
  └─→ Task 10 (SceneAssetsPanel)
Task 9 + 10
  └─→ Task 11 (smoke)
        └─→ Task 12 (README + DoD)
```

并行建议:Task 2 / 3 / 4 / 5 在 Task 1 合入后完全独立,可并行;Task 7 / 8 互不依赖,可并行。

## 附录 B:关键不变量速查

1. 所有写操作成功后必 `await workbench.reload()`,单一数据源来自 aggregate
2. 主 job 轮询入口只挂一次(panel setup);子 job id 不放大到 UI 级 watcher
3. `lockCharacter(as_protagonist=true)` 走 150s HTTP timeout,不走 job 轮询(后端同步返回,内部自轮询人像库);请求期间展示 persist info toast,finally dismiss
4. 任何被阶段门拦截的写按钮 → toast + 打开 `StageRollbackModal`(不直接 reload,用户选择)
5. `reference_image_url` 为 null 时 fallback 到 demo 装饰层;其余字段 null 展示占位文案 "(尚无描述)"
6. 42201 内容违规专门文案,其余未知错误码走 `utils/error.messageFor` fallback
7. 跨项目 job id 必须通过 `scopedJobId()` 过滤(M2 已建立,M3a 复用)

## 附录 C:风险与回滚

- **Task 0 未合入**:本 plan 所有前端任务应 block;若后端方侧拒绝补 `meta`/storyboard 时间字段/`bind_scene` body 契约/阶段错误码,前端不得靠兼容分支绕过,需先收敛后端契约再继续
- **主角锁定 150s timeout**:若真实人像库压力导致 > 150s,UI 会报超时;降级策略是让后端把人像库调用异步化(新开 job),前端改为轮询 — 此改动超出 M3a 范围,先观察再决定
  - **2026-04-22 更新**:已落地为下方 Task 14(异步化 + useJobPolling 接管)。本条风险关闭。
- **生成大批角色导致火山图像限流**:M3a 前端不做节流,由后端 Celery concurrency 兜底;若用户频繁重试 → 42901 toast 即可
- **视觉抖动**:`reference_image_url` 懒加载时,选中角色卡片会经历"占位 → 图片" 闪烁;MVP 接受该抖动,M3b 再做 skeleton 过渡

---

# M3a Review 增量(2026-04-22 追加)

> **触发**:Task 0–12 完成后做了一次完整 review。`npm run typecheck` 报 2 个 error、`npm test` 4 个 fail;主角锁定的 150s 客户端 timeout 在真实人像库压力下不可靠。把修复 + 异步化补成两个新 Task,**Task 13 必须先合,Task 14 依赖 Task 13 落地的 `projectsApi.getJobs`**。

## Review 摘要(必读)

| 严重级 | 位置 | 问题 |
| --- | --- | --- |
| Critical | `frontend/src/store/workbench.ts:149` | 调用了不存在的 `projectsApi.getJobs`,`vue-tsc` 报 TS2339,`npm run build` 挂 |
| Critical | `tests/unit/characters.api.spec.ts:21,39` / `tests/unit/scenes.api.spec.ts:22,38` | 4 个 `toHaveBeenCalledWith` 漏写 axios 第三参数 `{timeout}`,与实现不一致 → 4 fail |
| Important | `CharacterAssetsPanel.vue:222` / `SceneAssetsPanel.vue:228` | `selectedHasRegenJob` 用 `some(startsWith)` 判定,A 重生成中切到 B,B 的按钮也会显示"重生成中…(X%)" |
| Important | `WorkbenchView.vue:30-48` `loadCurrent` | 非 draft 阶段从不主动接管 in-flight `gen_characters`/`gen_scenes`/`lock_character_asset` job,F5 后进度 UI 与成功 reload 都丢 |
| Medium | `store/workbench.ts:292-303` | `markRegen{Succeeded,Failed}(kind,id)` 与 `byKey` 版本重叠,死代码 |
| Medium | `SceneEditorModal.vue:55-56` | "清空 theme" 不可达,产品上无法撤销主题(M3a 接受,加注释即可) |
| Medium | `store/workbench.ts:228-230` | 用后端 code `40901` 当本地单飞拦截信号,语义"借用"不严谨,但行为正确 |

## Task 13: M3a Review 修复(前置 / 阻塞 Task 14)

**Files:**
- Modify: `frontend/src/api/projects.ts`(新增 `getJobs`)
- Modify: `frontend/src/store/workbench.ts`(`findAndTrackGenStoryboardJob` 类型修复)
- Modify: `frontend/tests/unit/characters.api.spec.ts`(2 处 expect 补 timeout/body)
- Modify: `frontend/tests/unit/scenes.api.spec.ts`(2 处同上)
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`(`selectedHasRegenJob` / `selectedRegenProgress` 收紧到当前 selected id)
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`(同上)
- Modify: `frontend/src/store/workbench.ts`(删 `markRegenSucceeded` / `markRegenFailed` 的 `(kind, id)` 重载,只保留 byKey)

- [ ] **Step 1: `projects.ts` 新增 `getJobs`**

```ts
// frontend/src/api/projects.ts
import type { JobState } from "@/types/api";
// ...
getJobs(id: string): Promise<JobState[]> {
  return client.get(`/projects/${id}/jobs`).then((r) => r.data as JobState[]);
}
```

后端 `GET /api/v1/projects/{id}/jobs` M2 已存在(`smoke_m3a.sh` 也在用),无需改后端。

- [ ] **Step 2: 修 `workbench.findAndTrackGenStoryboardJob` 显式类型**

```ts
// frontend/src/store/workbench.ts
import type { JobState } from "@/types/api";
// ...
async function findAndTrackGenStoryboardJob() {
  if (!current.value) return;
  const jobs = await projectsApi.getJobs(current.value.id);
  const gsJob = jobs.find(
    (j: JobState) =>
      j.kind === "gen_storyboard" && (j.status === "queued" || j.status === "running")
  );
  if (gsJob) genStoryboardJob.value = { projectId: current.value.id, jobId: gsJob.id };
}
```

- [ ] **Step 3: 4 处 expect 补齐第三参数**

```ts
// tests/unit/characters.api.spec.ts
// generate
expect(spy).toHaveBeenCalledWith(
  "/projects/pid/characters/generate",
  { extra_hints: ["美强惨"] },
  { timeout: 60_000 }
);
// regenerate
expect(spy).toHaveBeenCalledWith(
  "/projects/pid/characters/c1/regenerate",
  {},
  { timeout: 60_000 }
);
```

```ts
// tests/unit/scenes.api.spec.ts
// generate
expect(spy).toHaveBeenCalledWith(
  "/projects/pid/scenes/generate",
  { template_whitelist: ["palace"] },
  { timeout: 60_000 }
);
// regenerate
expect(spy).toHaveBeenCalledWith(
  "/projects/pid/scenes/s1/regenerate",
  {},
  { timeout: 60_000 }
);
```

- [ ] **Step 4: 收紧 `selectedHasRegenJob` 与 `selectedRegenProgress`(2 个 panel)**

```ts
// CharacterAssetsPanel.vue
const selectedRegenJobId = computed(() =>
  selectedCharacter.value
    ? store.regenJobIdFor("character", selectedCharacter.value.id)
    : null
);
const selectedHasRegenJob = computed(() => !!selectedRegenJobId.value);
const selectedRegenProgress = computed(() =>
  selectedRegenJobId.value ? regenProgressByJobId.value[selectedRegenJobId.value] ?? 0 : 0
);
```

`SceneAssetsPanel.vue` 同 pattern,把 `"character:"` 换成 `"scene:"`,`selectedCharacter` 换成 `selectedScene`。

`activeCharacterRegenJobId` / `activeSceneRegenJobId` 给 `useJobPolling` 用的 ref **保持原样**(单飞约束:同一 panel 同一时间只跑一个 regen,所以 polling 只挂一个),只改 UI 显示侧的判定。

- [ ] **Step 5: 删除 `markRegenSucceeded(kind, id)` / `markRegenFailed(kind, id)` 重载**

```ts
// store/workbench.ts —— 删除 markRegenSucceeded / markRegenFailed 函数定义与 return 暴露
// 只保留 markRegenByKeySucceeded / markRegenByKeyFailed(panel 内已只用 byKey 版本)
```

- [ ] **Step 6: 自检**

```bash
cd frontend
npm run typecheck       # 期望:0 error
npm test                # 期望:0 fail
```

- [ ] **Step 7: Commit**

```
fix(frontend): M3a review — 补 projectsApi.getJobs / 修 4 处测试期望 / regen 进度按 selected id 收紧
```

---

## Task 14: 主角锁定异步化 + 进度条 UI

**Goal:** 把 `lock(as_protagonist=true)` 从"同步等 120s 人像库 + 客户端 150s timeout"改成"立即 ack(job_id) + 后端 celery task + 前端 useJobPolling + inline 进度 banner",对齐 generate 的 UX 一致性。**普通锁定(`as_protagonist=false`)继续保持同步**(无外部依赖、< 100ms,无需异步化)。

**Architecture:**
- 后端 lock 路由按 `as_protagonist` 分流:`true` → 入库 + 创建 `register_character_asset` job + 立即返回 `{job_id}`;`false` → 同步置 `locked=true` + 推进 stage,返回原 `{id, locked, is_protagonist}`。
- 后端 task `register_character_asset` 把 `ensure_character_asset_registered` 的 3 阶段(create_group / create_asset / wait_active)用 `update_job_progress(done, total=3)` 拆出来推进度。
- 前端 `charactersApi.lock` 返回 union `CharacterLockResponse | GenerateJobAck`(用 `ack` 字段或 discriminator 区分);store 加 `activeLockCharacterJobId` + `lockCharacterError`,Panel 套现成 `useJobPolling` + 与 generate 同款 banner。
- `loadCurrent` 接管 in-flight lock job(stage `storyboard_ready`/`characters_locked` 都查一次,因为推进 stage 是 task 末尾事件,可能还在 storyboard_ready)。

**Files:**

后端:
- Modify: `backend/app/domain/services/character_service.py`(`lock` 分流;抽 `_register_asset_steps` 给 task 复用)
- New:    `backend/app/tasks/ai/register_character_asset.py`(celery task,3 阶段进度)
- Modify: `backend/app/tasks/celery_app.py`(注册 task 到 `ai` 队列)
- Modify: `backend/app/domain/models/job.py`(jobs.kind enum 加 `register_character_asset`)
- Modify: `backend/app/domain/schemas/character.py`(lock response 改 union 或加 discriminator)
- New:    `backend/alembic/versions/<rev>_add_register_character_asset_job_kind.py`(若 kind 是数据库 enum 而非应用层枚举)
- Modify: `backend/app/api/characters.py`(分流路由)
- Modify: `backend/tests/integration/test_m3a_contract.py`(新增 `test_lock_protagonist_returns_job_ack` / `test_lock_non_protagonist_stays_sync`)

前端:
- Modify: `frontend/src/types/api.ts`(`CharacterLockResponse` 改 union)
- Modify: `frontend/src/api/characters.ts`(timeout 撤回 30s,响应类型更新)
- Modify: `frontend/src/store/workbench.ts`(新增 `activeLockCharacterJobId` / `lockCharacterError` / `lockCharacter` 返回值更新 / `mark*` helper)
- Modify: `frontend/src/views/WorkbenchView.vue`(`loadCurrent` 接管 in-flight `register_character_asset` job)
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`(替换 persist toast 为 inline banner;失败重试入口)
- Modify: `frontend/tests/unit/characters.api.spec.ts`(lock 返回 union 的两种形态)
- Modify: `frontend/tests/unit/workbench.m3a.store.spec.ts`(`lockCharacter(true)` 写入 `activeLockCharacterJobId`,`lockCharacter(false)` 走 sync + reload)
- Modify: `frontend/scripts/smoke_m3a.sh`(主角锁定改用 job 轮询)

### 后端实现

- [ ] **Step 1: 抽出 `_register_asset_steps(session, character, on_step)`**

把 `character_service.ensure_character_asset_registered` 改写成 3 个**显式**阶段并通过 `on_step(done, label)` 上报:

```python
# backend/app/domain/services/character_service.py
async def _register_asset_steps(
    session: AsyncSession,
    character: Character,
    on_step: Callable[[int, str], Awaitable[None]] | None = None,
) -> None:
    """1) create_group(若无) 2) create_asset 3) wait_active。幂等。"""
    if not character.reference_image_url:
        return
    video_ref = (character.video_style_ref or {}).copy()
    if video_ref.get("asset_id") and video_ref.get("asset_status") == "Active":
        if on_step: await on_step(3, "已入库,跳过")
        return

    asset_client = get_volcano_asset_client()  # 失败直接抛,task 层捕获

    if not video_ref.get("asset_group_id"):
        if on_step: await on_step(0, "创建 AssetGroup")
        group = await asset_client.create_asset_group(
            name=f"char_{character.id}",
            description=f"Project {character.project_id} - {character.name}",
        )
        video_ref["asset_group_id"] = group["Id"]

    if on_step: await on_step(1, "创建 Asset")
    if not video_ref.get("asset_id"):
        asset = await asset_client.create_asset(
            group_id=video_ref["asset_group_id"],
            url=build_asset_url(character.reference_image_url),
            name=character.name,
        )
        video_ref["asset_id"] = asset["Id"]
        video_ref["asset_status"] = "Pending"
        character.video_style_ref = video_ref
        await session.flush()

    if on_step: await on_step(2, "等待 Active")
    final = await asset_client.wait_asset_active(video_ref["asset_id"], timeout=180)
    video_ref["asset_status"] = final["Status"]
    video_ref["asset_updated_at"] = datetime.now(timezone.utc).isoformat()
    character.video_style_ref = video_ref
    await session.flush()
    if on_step: await on_step(3, "完成")
```

`ensure_character_asset_registered` 保留为薄 wrapper(`_register_asset_steps(session, character, on_step=None)`),其它调用方不破坏。

- [ ] **Step 2: 新建 celery task `register_character_asset`**

```python
# backend/app/tasks/ai/register_character_asset.py
from app.tasks.celery_app import celery
from app.infra.db import session_factory
from app.tasks.shared import update_job_progress  # M2 已建立的唯一 job 写入口
from app.domain.services.character_service import CharacterService
from app.pipeline.transitions import advance_to_characters_locked

@celery.task(name="ai.register_character_asset", queue="ai", bind=True)
def register_character_asset(self, job_id: str, project_id: str, character_id: str):
    import asyncio
    asyncio.run(_run(job_id, project_id, character_id))

async def _run(job_id: str, project_id: str, character_id: str) -> None:
    async with session_factory() as session:
        await update_job_progress(session, job_id, status="running", done=0, total=3)
        character = await session.get(Character, character_id)
        project = await session.get(Project, project_id)
        try:
            async def _on_step(done: int, label: str) -> None:
                await update_job_progress(session, job_id, done=done, total=3, status="running")
            await CharacterService._register_asset_steps(session, character, on_step=_on_step)
            # 入库成功后再尝试推进 stage(若主角已锁定)
            try:
                await advance_to_characters_locked(session, project)
            except Exception:
                pass
            await session.commit()
            await update_job_progress(session, job_id, status="succeeded", done=3, total=3)
        except Exception as e:
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            raise
```

注册到 `tasks/celery_app.py` 的 import 列表;路由按 `app.tasks.celery_app` 现有 `task_routes` 前缀 `ai.*` → `ai` 队列即可,不用新增路由规则。

- [ ] **Step 3: `Job.kind` 增加 `register_character_asset`**

如果 `jobs.kind` 是 SQLAlchemy `String` + 应用层 enum,只需在 `domain/models/job.py` 的 enum 类加常量;若是 DB 层 ENUM,补 alembic migration:

```python
# alembic/versions/<rev>_add_register_character_asset_job_kind.py
def upgrade():
    op.execute("""
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel','gen_storyboard','gen_character_asset','gen_scene_asset',
            'register_character_asset'
        ) NOT NULL
    """)

def downgrade():
    # 注意:回滚前须确保表里没有该 kind 行,否则 ALTER 会失败
    op.execute("DELETE FROM jobs WHERE kind = 'register_character_asset'")
    op.execute("""ALTER TABLE jobs MODIFY COLUMN kind ENUM(
        'parse_novel','gen_storyboard','gen_character_asset','gen_scene_asset'
    ) NOT NULL""")
```

执行者先用 `SHOW CREATE TABLE jobs` 确认实际列定义再选分支。

- [ ] **Step 4: `CharacterService.lock` 分流;新增 `lock_async`**

```python
@staticmethod
async def lock(
    session: AsyncSession, project: Project, character: Character,
    as_protagonist: bool = False,
) -> dict:
    """同步分支(as_protagonist=False):立即置锁 + 尝试推进 stage,返回 {id, locked, is_protagonist}"""
    assert_asset_editable(project, "character")
    character.locked = True
    try:
        await advance_to_characters_locked(session, project)
    except Exception:
        pass
    return {"id": character.id, "locked": True, "is_protagonist": character.is_protagonist}

@staticmethod
async def lock_protagonist_async(
    session: AsyncSession, project: Project, character: Character,
) -> str:
    """异步分支:同步完成 lock_protagonist(stage 转换 + 标主角)+ 投递 register_character_asset task,返回 job_id"""
    assert_asset_editable(project, "character")
    await lock_protagonist(session, project, character)  # 含主角降级 + locked=True
    job = await create_job(session, project_id=project.id, kind="register_character_asset")
    await session.commit()  # 先落库,再投递,避免 task 拿不到 job 行
    register_character_asset.delay(job.id, project.id, character.id)
    return job.id
```

- [ ] **Step 5: 路由分流**

```python
# backend/app/api/characters.py
@router.post("/{cid}/lock")
async def lock_character(cid: str, project_id: str = ..., req: CharacterLockRequest = ...,
                         db: AsyncSession = Depends(get_db)):
    project = await _get_project(db, project_id)
    char = await _get_character(db, cid)
    as_proto = bool(req and req.as_protagonist)
    if as_proto:
        job_id = await CharacterService.lock_protagonist_async(db, project, char)
        return Envelope.success({"job_id": job_id, "sub_job_ids": [], "ack": "async"})
    body = await CharacterService.lock(db, project, char, as_protagonist=False)
    return Envelope.success({**body, "ack": "sync"})
```

`ack` 字段是 discriminator,前端按它分支处理。`sub_job_ids` 给空数组以复用 `GenerateJobAck` 形状(前端可以走同一类型)。

- [ ] **Step 6: 后端契约测试**

```python
# backend/tests/integration/test_m3a_contract.py
async def test_lock_non_protagonist_stays_sync(client, project_storyboard_ready_with_chars):
    pid, cid = project_storyboard_ready_with_chars
    resp = await client.post(f"/projects/{pid}/characters/{cid}/lock", json={"as_protagonist": False})
    body = resp.json()["data"]
    assert body["ack"] == "sync"
    assert body["locked"] is True

async def test_lock_protagonist_returns_job_ack(client, project_storyboard_ready_with_chars):
    pid, cid = project_storyboard_ready_with_chars
    resp = await client.post(f"/projects/{pid}/characters/{cid}/lock", json={"as_protagonist": True})
    body = resp.json()["data"]
    assert body["ack"] == "async"
    assert body["job_id"]
    # CELERY_TASK_ALWAYS_EAGER=true 下 task 已同步执行完
    job = (await client.get(f"/jobs/{body['job_id']}")).json()["data"]
    assert job["status"] in ("succeeded", "failed")  # mock asset client 应当 succeeded
```

### 前端实现

- [ ] **Step 7: `types/api.ts` 把 `CharacterLockResponse` 改成 discriminated union**

```ts
// frontend/src/types/api.ts
export interface CharacterLockResponseSync {
  ack: "sync";
  id: string;
  locked: boolean;
  is_protagonist: boolean;
}
export interface CharacterLockResponseAsync extends GenerateJobAck {
  ack: "async";
}
export type CharacterLockResponse = CharacterLockResponseSync | CharacterLockResponseAsync;
```

- [ ] **Step 8: `api/characters.ts` 撤回 timeout**

```ts
// 异步分支几十 ms 即返回;同步分支也是本地 DB 操作。统一回到 client 默认 15s。
const LOCK_TIMEOUT_MS = 30_000; // 留 buffer 给慢网络
lock(projectId, characterId, payload): Promise<CharacterLockResponse> {
  return client
    .post(`/projects/${projectId}/characters/${characterId}/lock`, payload, { timeout: LOCK_TIMEOUT_MS })
    .then((r) => r.data as CharacterLockResponse);
}
```

- [ ] **Step 9: `store/workbench.ts` 新增 lock job 追踪**

```ts
const lockCharacterJob = ref<{ projectId: string; jobId: string; characterId: string } | null>(null);
const lockCharacterError = ref<string | null>(null);
const activeLockCharacterJobId = computed<string | null>(() =>
  scopedJobId(lockCharacterJob.value ? { projectId: lockCharacterJob.value.projectId, jobId: lockCharacterJob.value.jobId } : null)
);
const activeLockCharacterId = computed<string | null>(() =>
  lockCharacterJob.value && current.value && lockCharacterJob.value.projectId === current.value.id
    ? lockCharacterJob.value.characterId : null
);

async function lockCharacter(characterId: string, payload: CharacterLockRequest): Promise<void> {
  if (!current.value) throw new Error("lockCharacter: no current project");
  lockCharacterError.value = null;
  const resp = await charactersApi.lock(current.value.id, characterId, payload);
  if (resp.ack === "async") {
    lockCharacterJob.value = { projectId: current.value.id, jobId: resp.job_id, characterId };
    // 不 reload —— 等 job succeed 再 reload
    return;
  }
  await reload();
}
function markLockCharacterSucceeded() { lockCharacterJob.value = null; lockCharacterError.value = null; }
function markLockCharacterFailed(msg: string) { lockCharacterJob.value = null; lockCharacterError.value = msg; }
```

return 暴露 `activeLockCharacterJobId` / `activeLockCharacterId` / `lockCharacterError` / `markLockCharacter*`。

- [ ] **Step 10: `WorkbenchView.loadCurrent` 接管 in-flight job**

```ts
async function loadCurrent() {
  // ... store.load ...
  if (!store.current) return;
  if (store.current.stage_raw === "draft") {
    await store.findAndTrackGenStoryboardJob();
  } else {
    store.markParseSucceeded();
    // M3a Task 14: 接管 in-flight gen_characters / gen_scenes / register_character_asset
    await store.findAndTrackInFlightAssetJobs();
  }
}
```

`store.findAndTrackInFlightAssetJobs`:

```ts
async function findAndTrackInFlightAssetJobs() {
  if (!current.value) return;
  const jobs = await projectsApi.getJobs(current.value.id);
  const running = (kind: string) => jobs.find(
    (j: JobState) => j.kind === kind && (j.status === "queued" || j.status === "running")
  );
  const gc = running("gen_character_asset"); // 注意:与 backend kind 对齐,可能是 "gen_characters" 或 "gen_character_asset",以 backend 实际为准
  if (gc) generateCharactersJob.value = { projectId: current.value.id, jobId: gc.id };
  const gs = running("gen_scene_asset");
  if (gs) generateScenesJob.value = { projectId: current.value.id, jobId: gs.id };
  const rca = running("register_character_asset");
  if (rca) {
    // characterId 从 job.result/meta 读;若后端没存,降级为不显示具体角色,只显示 banner
    const cid = (rca.result as { character_id?: string } | null)?.character_id ?? "";
    lockCharacterJob.value = { projectId: current.value.id, jobId: rca.id, characterId: cid };
  }
}
```

⚠️ 后端在 `register_character_asset` task 投递时应把 `character_id` 写到 jobs 表的 `result`/`meta` 列(不写 result,因为 result 是终态)。补一个 `meta` 列写入,或用 `JobService.create_job(... meta={character_id})`。**Step 4 实现时同步落地。**

- [ ] **Step 11: `CharacterAssetsPanel.vue` 替换 persist toast 为 inline banner**

```vue
<script setup lang="ts">
const {
  // ...
  activeLockCharacterJobId,
  activeLockCharacterId,
  lockCharacterError
} = storeToRefs(store);

const { job: lockJob } = useJobPolling(activeLockCharacterJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markLockCharacterSucceeded();
      toast.success("主角已锁定并入库");
    } catch (e) {
      store.markLockCharacterFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg = j?.error_msg ?? (err instanceof ApiError ? messageFor(err.code, err.message) : "锁定失败");
    store.markLockCharacterFailed(msg);
    toast.error(msg);
  }
});

const lockProgressLabel = computed(() => {
  const j = lockJob.value;
  if (!j) return "正在排队…";
  const map: Record<number, string> = { 0: "创建 AssetGroup", 1: "创建 Asset", 2: "等待 Active", 3: "完成" };
  return `正在锁定主角… ${map[j.done] ?? `${j.done}/3`}`;
});

async function handleLock(asProtagonist: boolean) {
  // ... gate 检查与确认对话框保持原样,删掉 persist toast 与 dismiss 分支 ...
  busy.value = true;
  try {
    await store.lockCharacter(selectedCharacter.value!.id, { as_protagonist: asProtagonist });
    if (!asProtagonist) toast.success("角色已锁定"); // 异步分支等 onSuccess 再 toast
  } catch (e) {
    if (e instanceof ApiError && e.code === 42201) toast.error(messageFor(42201, e.message));
    else if (e instanceof ApiError) toast.error(messageFor(e.code, e.message));
    else toast.error("锁定失败");
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <!-- 在 generate banner 同位置加一个 lock banner;两者互斥 -->
  <div v-if="activeLockCharacterJobId" class="gen-banner running">
    <div class="gen-head">
      <strong>{{ lockProgressLabel }}</strong>
    </div>
    <ProgressBar :value="lockJob ? Math.round((lockJob.done / 3) * 100) : 0" />
    <p class="hint">正在调用人像库,通常 30–90 秒。可继续浏览,完成后会自动刷新。</p>
  </div>
  <div v-else-if="lockCharacterError" class="gen-banner error">
    <div class="gen-head">
      <strong>主角锁定失败</strong>
      <button class="ghost-btn small" @click="handleLock(true)">重试</button>
    </div>
    <p>{{ lockCharacterError }}</p>
  </div>
</template>
```

并把"设为主角 · 锁定"按钮在 `activeLockCharacterId === selectedCharacter.id` 时 `disabled`(避免重复触发)。

- [ ] **Step 12: 测试更新**

```ts
// tests/unit/characters.api.spec.ts —— lock 两种返回形态
it("lock(async) → 返回 ack=async + job_id", async () => {
  vi.spyOn(client, "post").mockResolvedValue({
    data: { ack: "async", job_id: "LJ1", sub_job_ids: [] }
  } as never);
  const r = await charactersApi.lock("pid", "c1", { as_protagonist: true });
  expect(r.ack).toBe("async");
  if (r.ack === "async") expect(r.job_id).toBe("LJ1");
});
it("lock(sync) → 返回 ack=sync + locked", async () => {
  vi.spyOn(client, "post").mockResolvedValue({
    data: { ack: "sync", id: "c1", locked: true, is_protagonist: false }
  } as never);
  const r = await charactersApi.lock("pid", "c1", { as_protagonist: false });
  expect(r.ack).toBe("sync");
  if (r.ack === "sync") expect(r.locked).toBe(true);
});
```

```ts
// tests/unit/workbench.m3a.store.spec.ts
it("lockCharacter(true): 写 activeLockCharacterJobId,不立即 reload", async () => {
  vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({ characters: [/* C1 */] }) as any);
  const lockSpy = vi.spyOn(charactersApi, "lock").mockResolvedValue({
    ack: "async", job_id: "LJ1", sub_job_ids: []
  } as any);
  const store = useWorkbenchStore();
  await store.load("P1");
  await store.lockCharacter("C1", { as_protagonist: true });
  expect(store.activeLockCharacterJobId).toBe("LJ1");
  expect(lockSpy).toHaveBeenCalledTimes(1);
  // 此处只 load 1 次(异步分支不 reload)
});
it("lockCharacter(false): 同步,完成后 reload", async () => {
  // ... mockResolvedValueOnce(...) 两次,断言 reload ...
});
```

- [ ] **Step 13: smoke_m3a.sh 主角锁定改用 job 轮询**

```bash
echo "[6/9] 锁定主角(异步)"
ack=$(curl -s -X POST "$API/projects/$pid/characters/$cid/lock" \
  -H "Content-Type: application/json" -d '{"as_protagonist": true}')
ljid=$(echo "$ack" | jq -r '.data.job_id')
[ "$(echo "$ack" | jq -r '.data.ack')" = "async" ] || { echo "expected async ack"; exit 1; }
for i in {1..150}; do
  st=$(curl -s "$API/jobs/$ljid" | jq -r '.data.status')
  echo "  lock job: $st"
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "lock failed"; exit 1; }
  sleep 2
done
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
[ "$stage_raw" = "characters_locked" ] || { echo "expected characters_locked"; exit 1; }
```

- [ ] **Step 14: 自检**

```bash
# 后端
cd backend && ./.venv/bin/pytest tests/integration/test_m3a_contract.py -v
./scripts/smoke_m3a.sh

# 前端
cd frontend && npm run typecheck && npm test && npm run build
./scripts/smoke_m3a.sh
```

- [ ] **Step 15: Commits(分两个,前后端各一)**

```
feat(backend): 主角入库异步化为 register_character_asset celery task,lock 路由按 as_protagonist 分流
feat(frontend): 主角锁定改 useJobPolling + inline 进度 banner,撤回 150s 长 timeout
```

## 增量 DoD

在原 ## DoD 基础上追加:

- [ ] Task 13 自检:`vue-tsc --noEmit` 0 error;`vitest run` 0 fail;手工:在角色 A 触发 regen,切到角色 B,B 的"重新生成参考图"按钮文案 + disable 状态 **不**受影响
- [ ] Task 14 自检:
  - [ ] 后端:`pytest tests/integration/test_m3a_contract.py::test_lock_protagonist_returns_job_ack` / `::test_lock_non_protagonist_stays_sync` 绿
  - [ ] 后端:`SHOW CREATE TABLE jobs` 包含 `register_character_asset` kind
  - [ ] 前端:`lock(true)` 立即返回 `ack=async`,UI 切换到进度 banner,而非 axios 长连接
  - [ ] 前端:在 lock job 进行中刷新页面,banner 由 `loadCurrent → findAndTrackInFlightAssetJobs` 自动接管,job succeed 后自动 reload
  - [ ] 前端:`lock(false)`(普通锁定)路径不变,仍是同步 + reload + toast
  - [ ] smoke_m3a.sh 的 [6/9] 步骤通过 job 轮询路径绿
- [ ] Task 15 自检:
  - [ ] 后端:`pytest tests/integration/test_m3a_contract.py::test_lock_scene_returns_job_ack` 绿
  - [ ] 后端:`SHOW CREATE TABLE jobs` 包含 `lock_scene_asset` kind
  - [ ] 前端:`lockScene()` 立即返回 `ack=async`,UI 切换到进度 banner,而非 axios 长连接
  - [ ] 前端:在 scene lock job 进行中刷新页面,banner 由 `loadCurrent → findAndTrackInFlightAssetJobs` 自动接管,job succeed 后自动 reload
  - [ ] 前端:当前锁定中的 scene 详情页按钮进入 disable/busy 态,其它 scene 不受影响
  - [ ] smoke_m3a.sh 的锁定场景步骤通过 job 轮询路径绿

## Task 15: 场景锁定异步化 + 进度条 UI

**Goal:** 把 `lockScene()` 从"同步锁定 + 立即 reload"改成"立即 ack(job_id) + 后端 celery task + 前端 useJobPolling + inline 进度 banner",让"场景设定"与 Task 14 的主角锁定保持同一套异步 UX,并避免场景锁定后推进 `scenes_locked` 时的 HTTP 长连接与刷新丢失状态问题。

**Architecture:**
- 后端 `POST /scenes/{sid}/lock` 改为统一异步 ack:创建 `lock_scene_asset` job,由 celery task 完成阶段校验、场景锁定、阶段推进与进度更新,HTTP 立即返回 `{job_id}`。
- task 把场景锁定拆成 3 个显式进度阶段:`校验阶段与绑定完整性` → `写入 locked=true` → `重新计算并推进 stage`;全部 job 状态写入必须继续走 `update_job_progress`。
- 前端 `scenesApi.lock` 返回 `GenerateJobAck` 同构形状(`ack: "async"` + `job_id`),store 新增 `activeLockSceneJobId` / `activeLockSceneId` / `lockSceneError`;`SceneAssetsPanel.vue` 使用 `useJobPolling` 渲染与 Task 14 同款 inline banner。
- `WorkbenchView.loadCurrent` / `workbench.findAndTrackInFlightAssetJobs` 扩展接管 `lock_scene_asset` 任务,保证刷新页面后仍能自动恢复 banner 与成功后的 `reload()`。

**Files:**

后端:
- Modify: `backend/app/domain/services/scene_service.py`(`lock` 分流为异步投递;抽 `_lock_scene_steps` 供 task 复用)
- New:    `backend/app/tasks/ai/lock_scene_asset.py`(celery task,3 阶段进度)
- Modify: `backend/app/tasks/celery_app.py`(注册 task 到 `ai` 队列)
- Modify: `backend/app/domain/models/job.py`(jobs.kind enum 加 `lock_scene_asset`)
- Modify: `backend/app/domain/schemas/scene.py`(lock response 改为 async ack 形状或 union)
- New:    `backend/alembic/versions/<rev>_add_lock_scene_asset_job_kind.py`(若 kind 是数据库 enum)
- Modify: `backend/app/api/scenes.py`(lock 路由改立即 ack)
- Modify: `backend/tests/integration/test_m3a_contract.py`(新增 `test_lock_scene_returns_job_ack` / `test_lock_scene_job_advances_stage_when_ready`)

前端:
- Modify: `frontend/src/types/api.ts`(`SceneLockResponse` 改为 discriminated union 或直接复用 `GenerateJobAck`)
- Modify: `frontend/src/api/scenes.ts`(lock 返回 async ack,不再依赖同步 reload 语义)
- Modify: `frontend/src/store/workbench.ts`(新增 `activeLockSceneJobId` / `activeLockSceneId` / `lockSceneError` / `markLockScene*`)
- Modify: `frontend/src/views/WorkbenchView.vue`(`loadCurrent` 接管 in-flight `lock_scene_asset` job)
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`(新增锁定场景进度 banner;失败重试入口;当前 scene busy 态)
- Modify: `frontend/tests/unit/scenes.api.spec.ts`(lock 返回 async ack)
- Modify: `frontend/tests/unit/workbench.m3a.store.spec.ts`(`lockScene()` 写入 `activeLockSceneJobId`,不立即 reload)
- Modify: `frontend/scripts/smoke_m3a.sh`(锁定场景步骤改用 job 轮询)

### 后端实现

- [ ] **Step 1: 抽出 `_lock_scene_steps(session, project, scene, on_step)`**

把 `SceneService.lock` 改成可被 task 复用的显式 3 步流程,并通过 `on_step(done, label)` 上报:

```python
# backend/app/domain/services/scene_service.py
async def _lock_scene_steps(
    session: AsyncSession,
    project: Project,
    scene: Scene,
    on_step: Callable[[int, str], Awaitable[None]] | None = None,
) -> None:
    assert_asset_editable(project, "scene")

    if on_step:
        await on_step(0, "校验场景与镜头绑定")
    # 保留现有锁定前校验:
    # 1. scene 属于当前 project
    # 2. 若业务要求"进入 scenes_locked 前所有镜头均已绑定",则在这里做可重复校验

    if on_step:
        await on_step(1, "写入锁定状态")
    scene.locked = True
    await session.flush()

    if on_step:
        await on_step(2, "重新计算项目阶段")
    try:
        await advance_to_scenes_locked(session, project)
    except InvalidTransition:
        # 允许当前 scene 已锁定,但项目仍停留在 characters_locked
        pass

    if on_step:
        await on_step(3, "完成")
```

`SceneService.lock` 保留为薄 wrapper,供测试或其它同步调用方复用,避免锁定规则散落到 router / task。

- [ ] **Step 2: 新建 celery task `lock_scene_asset`**

```python
# backend/app/tasks/ai/lock_scene_asset.py
from app.tasks.celery_app import celery
from app.infra.db import session_factory
from app.tasks.shared import update_job_progress
from app.domain.services.scene_service import SceneService

@celery.task(name="ai.lock_scene_asset", queue="ai", bind=True)
def lock_scene_asset(self, job_id: str, project_id: str, scene_id: str):
    import asyncio
    asyncio.run(_run(job_id, project_id, scene_id))

async def _run(job_id: str, project_id: str, scene_id: str) -> None:
    async with session_factory() as session:
      await update_job_progress(session, job_id, status="running", done=0, total=3)
      project = await session.get(Project, project_id)
      scene = await session.get(Scene, scene_id)
      try:
          async def _on_step(done: int, label: str) -> None:
              await update_job_progress(session, job_id, done=done, total=3, status="running")

          await SceneService._lock_scene_steps(session, project, scene, on_step=_on_step)
          await session.commit()
          await update_job_progress(session, job_id, status="succeeded", done=3, total=3)
      except Exception as e:
          await session.rollback()
          await update_job_progress(session, job_id, status="failed", error_msg=str(e))
          raise
```

投递 job 时把 `scene_id` 写入 `jobs.payload` / `jobs.meta`,供前端刷新后精确恢复当前锁定中的 scene。

- [ ] **Step 3: `Job.kind` 增加 `lock_scene_asset`**

若 `jobs.kind` 是 DB ENUM,补 migration:

```python
def upgrade():
    op.execute("""
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel','gen_storyboard','gen_character_asset','gen_scene_asset',
            'register_character_asset','lock_scene_asset'
        ) NOT NULL
    """)
```

先用 `SHOW CREATE TABLE jobs` 确认实际列类型;若只是应用层枚举,只改 `domain/models/job.py` 即可。

- [ ] **Step 4: `SceneService.lock_async` + 路由立即 ack**

```python
@staticmethod
async def lock_async(session: AsyncSession, project: Project, scene: Scene) -> str:
    assert_asset_editable(project, "scene")
    job = await create_job(
        session,
        project_id=project.id,
        kind="lock_scene_asset",
        payload={"scene_id": scene.id},
    )
    await session.commit()
    lock_scene_asset.delay(job.id, project.id, scene.id)
    return job.id
```

```python
# backend/app/api/scenes.py
@router.post("/{sid}/lock")
async def lock_scene(...):
    project = await _get_project(db, project_id)
    scene = await _get_scene(db, sid)
    job_id = await SceneService.lock_async(db, project, scene)
    return Envelope.success({
        "ack": "async",
        "job_id": job_id,
        "sub_job_ids": [],
    })
```

这样前端与 `generateScenes` / Task 14 lock protagonist 共用同一套 ack 处理逻辑,避免 `lockScene` 继续保留一个特殊同步分支。

- [ ] **Step 5: 后端契约测试**

```python
async def test_lock_scene_returns_job_ack(client, project_with_bindable_scene):
    pid, scene_id = project_with_bindable_scene
    resp = await client.post(f"/projects/{pid}/scenes/{scene_id}/lock", json={})
    body = resp.json()["data"]
    assert body["ack"] == "async"
    assert body["job_id"]

async def test_lock_scene_job_advances_stage_when_ready(client, project_with_all_bound_locked_ready):
    pid, scene_id = project_with_all_bound_locked_ready
    resp = await client.post(f"/projects/{pid}/scenes/{scene_id}/lock", json={})
    job_id = resp.json()["data"]["job_id"]
    job = (await client.get(f"/jobs/{job_id}")).json()["data"]
    assert job["status"] in ("succeeded", "failed")
    project = (await client.get(f"/projects/{pid}")).json()["data"]
    assert project["stage_raw"] in ("characters_locked", "scenes_locked")
```

`CELERY_TASK_ALWAYS_EAGER=true` 下可直接断言 job 终态与聚合 `stage_raw`;若 fixture 已满足"所有镜头都已绑定到已锁定场景",则断言最终为 `scenes_locked`。

### 前端实现

- [ ] **Step 6: `types/api.ts` 更新 `SceneLockResponse`**

建议直接与 Task 14 对齐:

```ts
export interface SceneLockResponseAsync extends GenerateJobAck {
  ack: "async";
}

export type SceneLockResponse = SceneLockResponseAsync;
```

若后端保留 union 也可以,但本任务推荐统一 async,减少 store 分支。

- [ ] **Step 7: `api/scenes.ts` 返回 async ack**

```ts
lock(projectId: string, sceneId: string): Promise<SceneLockResponse> {
  return client
    .post(`/projects/${projectId}/scenes/${sceneId}/lock`, {}, { timeout: 30_000 })
    .then((r) => r.data as SceneLockResponse);
}
```

不再假设 lock 完成后 HTTP 返回时数据已落库;落库以 job succeed 后 `reload()` 为准。

- [ ] **Step 8: `store/workbench.ts` 新增 scene lock job 追踪**

```ts
const lockSceneJob = ref<{ projectId: string; jobId: string; sceneId: string } | null>(null);
const lockSceneError = ref<string | null>(null);

const activeLockSceneJobId = computed<string | null>(() =>
  current.value && lockSceneJob.value && lockSceneJob.value.projectId === current.value.id
    ? lockSceneJob.value.jobId
    : null
);

const activeLockSceneId = computed<string | null>(() =>
  lockSceneJob.value && current.value && lockSceneJob.value.projectId === current.value.id
    ? lockSceneJob.value.sceneId
    : null
);

async function lockScene(sceneId: string): Promise<void> {
  if (!current.value) throw new Error("lockScene: no current project");
  lockSceneError.value = null;
  const resp = await scenesApi.lock(current.value.id, sceneId);
  lockSceneJob.value = { projectId: current.value.id, jobId: resp.job_id, sceneId };
}

function markLockSceneSucceeded() {
  lockSceneJob.value = null;
  lockSceneError.value = null;
}

function markLockSceneFailed(msg: string) {
  lockSceneJob.value = null;
  lockSceneError.value = msg;
}
```

并在 `findAndTrackInFlightAssetJobs` 中新增:

```ts
const lsaJob = running("lock_scene_asset");
if (lsaJob) {
  const sid = (lsaJob.payload as { scene_id?: string } | null)?.scene_id ?? "";
  lockSceneJob.value = {
    projectId: current.value.id,
    jobId: lsaJob.id,
    sceneId: sid
  };
} else {
  const failed = lastFailed("lock_scene_asset");
  if (failed) lockSceneError.value = failed.error_msg;
}
```

- [ ] **Step 9: `WorkbenchView.vue` 刷新恢复 in-flight scene lock**

沿用 Task 14 的接管点,不新增第二套入口;只确保 `loadCurrent()` 调用的 `findAndTrackInFlightAssetJobs()` 已覆盖 `lock_scene_asset`。这样页面刷新后 `SceneAssetsPanel` 能直接根据 `activeLockSceneJobId` 恢复 banner。

- [ ] **Step 10: `SceneAssetsPanel.vue` 新增锁定场景进度 banner**

```vue
const {
  activeLockSceneJobId,
  activeLockSceneId,
  lockSceneError
} = storeToRefs(store);

const { job: lockJob } = useJobPolling(activeLockSceneJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markLockSceneSucceeded();
      toast.success("场景已锁定");
    } catch (e) {
      store.markLockSceneFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "锁定失败");
    store.markLockSceneFailed(msg);
    toast.error(msg);
  }
});

const lockProgressLabel = computed(() => {
  const j = lockJob.value;
  if (!j) return "正在排队…";
  const stepMap: Record<number, string> = {
    0: "校验场景与绑定",
    1: "写入锁定状态",
    2: "重新计算项目阶段",
    3: "完成"
  };
  return `正在锁定场景… ${stepMap[j.done] ?? `${j.done}/3`}`;
});
```

模板层增加与 Task 14 同位的 banner:

```vue
<div v-if="activeGenerateScenesJobId" class="gen-banner running">...</div>
<div v-else-if="activeLockSceneJobId" class="gen-banner running">
  <div class="gen-head">
    <strong>{{ lockProgressLabel }}</strong>
  </div>
  <ProgressBar :value="lockJob ? Math.round((lockJob.done / 3) * 100) : 0" />
  <p class="hint">正在锁定场景并同步项目阶段,完成后会自动刷新。</p>
</div>
<div v-else-if="generateScenesError" class="gen-banner error">...</div>
<div v-else-if="lockSceneError" class="gen-banner error">
  <div class="gen-head">
    <strong>场景锁定失败</strong>
    <button class="ghost-btn small" @click="handleLock">重试</button>
  </div>
  <p>{{ lockSceneError }}</p>
</div>
```

并把当前选中 scene 的"锁定场景"按钮在 `activeLockSceneId === selectedScene.id` 时禁用,文案可切为 `"锁定中..."`;其它 scene 继续可切换查看。

- [ ] **Step 11: 测试更新**

```ts
// tests/unit/scenes.api.spec.ts
it("lock(async) → 返回 ack=async + job_id", async () => {
  vi.spyOn(client, "post").mockResolvedValue({
    data: { ack: "async", job_id: "SJ1", sub_job_ids: [] }
  } as never);
  const r = await scenesApi.lock("pid", "s1");
  expect(r.ack).toBe("async");
  expect(r.job_id).toBe("SJ1");
});
```

```ts
// tests/unit/workbench.m3a.store.spec.ts
it("lockScene(): 写 activeLockSceneJobId,不立即 reload", async () => {
  vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({ scenes: [/* S1 */] }) as any);
  vi.spyOn(scenesApi, "lock").mockResolvedValue({
    ack: "async", job_id: "SJ1", sub_job_ids: []
  } as any);
  const store = useWorkbenchStore();
  await store.load("P1");
  await store.lockScene("S1");
  expect(store.activeLockSceneJobId).toBe("SJ1");
});
```

增加一条面板级测试或 store 断言:当 `lockSceneJob.sceneId = "S1"` 时,`selectedScene = "S2"` 不应误显示 `"锁定中..."`。

- [ ] **Step 12: smoke_m3a.sh 锁定场景步骤改 job 轮询**

```bash
echo "[8/9] 锁定场景(异步)"
ack=$(curl -s -X POST "$API/projects/$pid/scenes/$sid/lock" \
  -H "Content-Type: application/json" -d '{}')
sjid=$(echo "$ack" | jq -r '.data.job_id')
[ "$(echo "$ack" | jq -r '.data.ack')" = "async" ] || { echo "expected async ack"; exit 1; }
for i in {1..150}; do
  st=$(curl -s "$API/jobs/$sjid" | jq -r '.data.status')
  echo "  scene lock job: $st"
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "scene lock failed"; exit 1; }
  sleep 2
done
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
[ "$stage_raw" = "scenes_locked" ] || { echo "expected scenes_locked"; exit 1; }
```

- [ ] **Step 13: 自检**

```bash
# 后端
cd backend && ./.venv/bin/pytest tests/integration/test_m3a_contract.py -v
./scripts/smoke_m3a.sh

# 前端
cd frontend && npm run typecheck && npm test && npm run build
./scripts/smoke_m3a.sh
```

- [ ] **Step 14: Commits(分两个,前后端各一)**

```
feat(backend): 场景锁定异步化为 lock_scene_asset celery task
feat(frontend): 场景锁定改 useJobPolling + inline 进度 banner
```

## 增量附录

### 附录 D:Task 14 受影响的不变量(覆盖原附录 B 第 3 条)

3'. ~~`lockCharacter(as_protagonist=true)` 走 150s HTTP timeout,不走 job 轮询~~ → **(Task 14)** `lockCharacter(true)` 走异步 job 轮询(`activeLockCharacterJobId` + `useJobPolling`);`lockCharacter(false)` 仍同步 + reload。两条路径在 store 内同名 action 内分流,UI 只关心 `activeLockCharacterJobId` 是否非空决定要不要渲染 banner。

8. **(新增)** `register_character_asset` task 必须把 `character_id` 写入 jobs.meta(或 result),以便前端 `findAndTrackInFlightAssetJobs` 在刷新后能定位被锁的角色。如果 backend 未来重命名该 kind,前端 `WorkbenchView.findAndTrackInFlightAssetJobs` 与 smoke 脚本的 jq 过滤需同步更新。

9. **(新增 / Task 15)** `lockScene()` 不再依赖同步 HTTP 完成锁定与阶段推进,而是统一走异步 job 轮询(`activeLockSceneJobId` + `useJobPolling`)。场景是否已真正锁定、项目是否已进入 `scenes_locked`,一律以后端 job succeed 后的 `reload()` 聚合快照为准。

10. **(新增 / Task 15)** `lock_scene_asset` task 必须把 `scene_id` 写入 jobs.payload/meta,以便前端在刷新页面后恢复当前锁定中的 scene 并仅禁用对应详情区按钮。如果 backend 未来重命名该 kind,前端 `findAndTrackInFlightAssetJobs` 与 smoke 脚本的 jq 过滤需同步更新。

### 附录 E:Task 14 / 15 任务依赖图

```
Task 13 (review fix)
  ├─→ Task 14 后端 Step 1-6 (service / task / routes / migration / tests)
  └─→ Task 14 前端 Step 7-13 (types / api / store / view / panel / tests / smoke)
        ↑
        必须等 Task 14 后端 merged,前端才能联调(因为 lock 响应形状变了)

Task 14
  ├─→ Task 15 后端 Step 1-5 (scene service / task / routes / migration / tests)
  └─→ Task 15 前端 Step 6-12 (types / api / store / view / panel / tests / smoke)
        ↑
        推荐在 Task 14 完成后复用同一套 lock job 追踪与 banner 模式,减少前后端分叉
```
