# Frontend M3b: 镜头渲染草稿编辑 + 确认生成 + 历史版本切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M3a 已交付的工作台基础上，把 `GenerationPanel` 从静态占位升级为“先生成草稿、用户临时编辑提示词和参考图、确认后再真正生成”的 M3b 镜头生成页，打通单镜头异步渲染、历史版本查看与切换、最终版锁定、刷新后 in-flight job 恢复，以及与后端 M3b draft/job/aggregate 契约一致的 UI。

**Architecture:** 延续 M2/M3a 的原则：HTTP 写操作只拿 ack / 同步结果，真正的状态来源统一以 `GET /projects/{id}` 聚合快照为准；前端不做乐观合并。M3b 前端先调用 `POST /render-draft` 获取后端建议的 prompt 和 reference images，在本地临时编辑后，再调用 `POST /render` 真正创建 job；未确认的草稿不落库。M3b 前端只支持“同一项目一次只发起一个镜头 render_shot job”，避免在 `GenerationPanel` 里再造并发调度器；批量继续生成、全量重渲、锁定全部最终版仍留给 M3c/M4。后端 `generationQueue` 在 M3b 继续保持 job-based 语义，前端在 panel 内把它和 `storyboards[]` 组合成 shot-centric 视图模型。

**Tech Stack:** Vue 3.5 `<script setup>` / TypeScript 5.7 strict / Pinia 2 / Axios 1.x / Vitest 2 / @vue/test-utils / 现有 `useJobPolling` / 现有 `useStageGate`。

---

## References

- 前端 spec: `docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §7.3.5、§8、§9、§15 M3b
- 后端 M3b plan: `docs/superpowers/plans/2026-04-22-backend-m3b-render-shot.md`
- 前端 M3a plan: `docs/superpowers/plans/2026-04-21-frontend-m3a-characters-scenes.md`
- 现有实现基线:
  - `frontend/src/store/workbench.ts`
  - `frontend/src/components/generation/GenerationPanel.vue`
  - `frontend/src/composables/useJobPolling.ts`
  - `frontend/src/composables/useStageGate.ts`
  - `frontend/src/types/index.ts`
  - `frontend/src/types/api.ts`

## Scope

**Includes:**

- 新增 `src/api/shots.ts`，对接后端 M3b 四条 shots 端点
- `types/api.ts` / `types/index.ts` 扩展 render 相关契约与 panel 视图类型
- `store/workbench.ts` 新增单镜头 render job 追踪、render draft 临时状态、历史版本缓存、同步选择/锁定动作
- `GenerationPanel.vue` 重写为真实可交互页：shot 列表、render draft、提示词编辑、参考图可删改、确认生成、历史版本、失败提示、锁定最终版
- 新组件 `RenderVersionHistory.vue` / `RenderRetryBanner.vue`
- `loadCurrent → findAndTrackActiveJobs` 扩展恢复 `render_shot` 任务
- `SceneAssetsPanel.vue` 移除“绑定镜头 → 此场景”按钮和对应入口
- `frontend/scripts/smoke_m3b.sh` 与 README 的 M3b 说明

**Excludes:**

- 批量继续生成 / 全量重渲 / 父子 job 聚合。这是 M3c。
- “锁定全部为最终版” 快捷按钮。后端 M3b 未提供批量 lock 端点。
- 导出面板联动、缺失镜头 modal、导出跳转。这是 M4。
- 并行多镜头 render 的前端调度器。M3b UI 只允许一次一个 `render_shot` job。

## Current Baseline Notes

- `GenerationPanel.vue` 目前仍是 demo 占位，只读 `current.generationQueue[0]`，没有任何真实写操作，也没有 prompt / references 的草稿编辑态。
- `useStageGate.ts` 已有 `canRender` / `canLockShot` 布尔，M3b 不需要新 gate，只要补覆盖测试。
- `workbench.ts` 已有 parse / generateCharacters / generateScenes / lockCharacter 的异步 job 追踪范式；M3b 复用它，不再新建单独 jobs store。
- 后端 M3b 聚合的 `generationQueue` 保持 job-based，不会直接给“一行一个 shot”的完整列表；前端必须自己从 `storyboards[]` 生成左侧列表。

## File Structure

**Create:**

```text
frontend/src/api/shots.ts
frontend/src/components/generation/RenderRetryBanner.vue
frontend/src/components/generation/RenderVersionHistory.vue
frontend/tests/unit/scene.assets.panel.spec.ts
frontend/tests/unit/shots.api.spec.ts
frontend/tests/unit/workbench.m3b.store.spec.ts
frontend/tests/unit/generation.panel.spec.ts
frontend/scripts/smoke_m3b.sh
```

**Modify:**

```text
frontend/src/types/api.ts
frontend/src/types/index.ts
frontend/src/store/workbench.ts
frontend/src/components/generation/GenerationPanel.vue
frontend/src/components/scene/SceneAssetsPanel.vue
frontend/src/composables/useStageGate.ts
frontend/tests/unit/useStageGate.spec.ts
frontend/src/views/WorkbenchView.vue
frontend/README.md
```

## Task 0: Contract Gate — 先核对后端 M3b 契约

**Files:**
- Verify: `docs/superpowers/plans/2026-04-22-backend-m3b-render-shot.md`
- Verify backend API against running service

- [ ] **Step 1: 核对 shots 端点与 ack 形状**

确认后端已提供并且形状一致：

```bash
curl -s http://127.0.0.1:8000/api/v1/projects/<pid>/shots/<sid>/renders | jq .

curl -s -X POST http://127.0.0.1:8000/api/v1/projects/<pid>/shots/<sid>/render-draft | jq .

curl -s -X POST http://127.0.0.1:8000/api/v1/projects/<pid>/shots/<sid>/render | jq .
```

预期：

- `POST /render-draft` 返回 `{ shot_id, prompt, references[] }`
- `POST /render` 返回 `{ "job_id": "...", "sub_job_ids": [] }`
- `GET /renders` 返回版本数组，字段至少包含:
  - `id`
  - `version_no`
  - `status`
  - `image_url`
  - `prompt_snapshot`
  - `error_code`
  - `error_msg`
  - `is_current`

- [ ] **Step 2: 核对聚合 detail 的 M3b 字段**

```bash
curl -s http://127.0.0.1:8000/api/v1/projects/<pid> \
  | jq '.data | {stage_raw,generationQueue,generationNotes,storyboards}'
```

预期：

- `generationQueue` 仍是 job-based 列表，而不是 shot-based 列表
- `generationQueue[*]` 对 `kind=="render_shot"` 的项追加:
  - `target_id`（必需；前端恢复 in-flight render 和 queue 命中都靠它）
  - `shot_id`（可选别名；若后端补了可直接复用，但前端实现不能依赖它）
  - `render_id`
  - `image_url`
  - `version_no`
  - `shot_status`
  - `error_code`
  - `error_msg`
- `GET /projects/{id}/jobs` 至少暴露：
  - `target_id`
  - `payload`
  - `result`
  - `error_msg`
  - `total`
  - `done`
  - `finished_at`
- `storyboards[*]` 保持:
  - `status`
  - `current_render_id`

- [ ] **Step 3: 不满足时先阻塞前端任务**

若后端缺任一契约，不要进入前端实现，先在 PR / 文档中补齐。尤其是下面四项若不满足，M3b 前端所有任务都 block：

- `POST /render` 不是标准 `GenerateJobAck`
- `generationQueue` 不是 job-based 追加字段，而是被后端重写成 shot-based
- `generationQueue[*]` 的 `render_shot` 项没有 `target_id`
- `GET /projects/{id}/jobs` 没有 `target_id/payload/result/error_msg`

## Task 1: Render Types 与 Stage Gate 覆盖

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/tests/unit/useStageGate.spec.ts`

- [ ] **Step 1: 写 failing types / gate 测试**

追加到 `frontend/tests/unit/useStageGate.spec.ts`:

```ts
import { gateFlags } from "@/composables/useStageGate";

it("render gate: scenes_locked 与 rendering 可渲染", () => {
  expect(gateFlags("scenes_locked").canRender).toBe(true);
  expect(gateFlags("rendering").canRender).toBe(true);
  expect(gateFlags("ready_for_export").canRender).toBe(false);
});

it("lock shot gate: rendering / ready_for_export 可锁定", () => {
  expect(gateFlags("rendering").canLockShot).toBe(true);
  expect(gateFlags("ready_for_export").canLockShot).toBe(true);
  expect(gateFlags("scenes_locked").canLockShot).toBe(false);
});
```

- [ ] **Step 2: 运行测试确认当前缺少 render types**

```bash
cd frontend
npm run test -- shots.api.spec.ts useStageGate.spec.ts
```

预期：`shots.api.spec.ts` 不存在，gate 用例可先通过或等待后续 task 一起跑。

- [ ] **Step 3: 扩展 API 与视图类型**

更新 `frontend/src/types/api.ts`：在**现有** `JobState` 接口上追加可选字段，不要整段重复定义，否则会出现 TS duplicate identifier。

```ts
export interface RenderDraftReference {
  id: string;
  kind: string;
  source_id: string;
  name: string;
  image_url: string;
  reason: string;
}

export interface RenderDraftRead {
  shot_id: string;
  prompt: string;
  references: RenderDraftReference[];
}

export interface RenderSubmitReference {
  id: string;
  kind: string;
  source_id: string;
  name: string;
  image_url: string;
}

export interface RenderSubmitRequest {
  prompt: string;
  references: RenderSubmitReference[];
}

export interface RenderVersionRead {
  id: string;
  shot_id: string;
  version_no: number;
  status: string;
  prompt_snapshot: Record<string, unknown> | null;
  image_url: string | null;
  provider_task_id: string | null;
  error_code: string | null;
  error_msg: string | null;
  created_at: string;
  finished_at: string | null;
  is_current: boolean;
}

export interface JobState {
  target_type?: string | null;
  target_id?: string | null;
}
```

更新 `frontend/src/types/index.ts`：

```ts
export interface RenderQueueItem {
  id: string; // 仍是 job.id,不是 shot.id
  kind: string;
  status: RenderStatus;
  progress: number;
  target_id?: string | null;
  shot_id?: string | null;
  render_id?: string | null;
  image_url?: string | null;
  version_no?: number | null;
  shot_status?: string | null;
  error_code?: string | null;
  error_msg?: string | null;
}

export interface RenderShotItem {
  shotId: string;
  title: string;
  summary: string;
  shotStatus: string;
  status: RenderStatus;
  progress: number;
  currentRenderId: string | null;
  imageUrl: string | null;
  versionNo: number | null;
  activeJobId: string | null;
  errorCode: string | null;
  errorMsg: string | null;
}
```

说明：

- `ProjectData.generationQueue` 继续保持后端 job-based 原样
- `RenderShotItem` 是前端 panel 内部组合出的 view model，不写回 API 层

- [ ] **Step 4: 跑测试**

```bash
cd frontend
npm run test -- useStageGate.spec.ts
```

预期：通过。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/types/index.ts frontend/tests/unit/useStageGate.spec.ts
git commit -m "feat(frontend): add m3b render types  (Task M3b-FE-1)"
```

## Task 2: Shots API Client

**Files:**
- Create: `frontend/src/api/shots.ts`
- Test: `frontend/tests/unit/shots.api.spec.ts`

- [ ] **Step 1: 写 failing API tests**

创建 `frontend/tests/unit/shots.api.spec.ts`:

```ts
import { describe, it, expect, vi } from "vitest";
import { client } from "@/api/client";
import { shotsApi } from "@/api/shots";

vi.mock("@/api/client", () => ({
  client: {
    post: vi.fn(),
    get: vi.fn()
  }
}));

describe("shotsApi", () => {
  it("renderDraft(): POST /shots/:id/render-draft", async () => {
    vi.mocked(client.post).mockResolvedValue({
      data: { shot_id: "S1", prompt: "图片1中的宫门，图片2中的主角。", references: [] }
    } as never);
    const draft = await shotsApi.renderDraft("P1", "S1");
    expect(client.post).toHaveBeenCalledWith("/projects/P1/shots/S1/render-draft");
    expect(draft.shot_id).toBe("S1");
  });

  it("render(): POST /shots/:id/render and returns GenerateJobAck", async () => {
    vi.mocked(client.post).mockResolvedValue({
      data: { job_id: "J1", sub_job_ids: [] }
    } as never);
    const ack = await shotsApi.render("P1", "S1", {
      prompt: "图片1中的宫门，图片2中的主角。",
      references: []
    });
    expect(client.post).toHaveBeenCalledWith("/projects/P1/shots/S1/render", {
      prompt: "图片1中的宫门，图片2中的主角。",
      references: []
    });
    expect(ack.job_id).toBe("J1");
  });

  it("listRenders(): GET render history", async () => {
    vi.mocked(client.get).mockResolvedValue({
      data: [{ id: "R1", version_no: 1, status: "succeeded", is_current: true }]
    } as never);
    const rows = await shotsApi.listRenders("P1", "S1");
    expect(client.get).toHaveBeenCalledWith("/projects/P1/shots/S1/renders");
    expect(rows[0].id).toBe("R1");
  });

  it("selectRender(): POST select endpoint", async () => {
    vi.mocked(client.post).mockResolvedValue({
      data: { shot_id: "S1", current_render_id: "R2", status: "succeeded" }
    } as never);
    const resp = await shotsApi.selectRender("P1", "S1", "R2");
    expect(client.post).toHaveBeenCalledWith("/projects/P1/shots/S1/renders/R2/select");
    expect(resp.current_render_id).toBe("R2");
  });
});
```

- [ ] **Step 2: 运行测试确认缺文件**

```bash
cd frontend
npm run test -- shots.api.spec.ts
```

预期：失败，提示 `@/api/shots` 不存在。

- [ ] **Step 3: 实现 API client**

创建 `frontend/src/api/shots.ts`:

```ts
import { client } from "./client";
import type {
  GenerateJobAck,
  RenderDraftRead,
  RenderSubmitRequest,
  RenderVersionRead
} from "@/types/api";

export interface SelectRenderResponse {
  shot_id: string;
  current_render_id: string;
  status: string;
}

export interface LockShotResponse {
  shot_id: string;
  status: string;
  current_render_id: string | null;
}

export const shotsApi = {
  renderDraft(projectId: string, shotId: string): Promise<RenderDraftRead> {
    return client
      .post(`/projects/${projectId}/shots/${shotId}/render-draft`)
      .then((r) => r.data as RenderDraftRead);
  },
  render(projectId: string, shotId: string, payload: RenderSubmitRequest): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/shots/${shotId}/render`, payload)
      .then((r) => r.data as GenerateJobAck);
  },
  listRenders(projectId: string, shotId: string): Promise<RenderVersionRead[]> {
    return client
      .get(`/projects/${projectId}/shots/${shotId}/renders`)
      .then((r) => r.data as RenderVersionRead[]);
  },
  selectRender(projectId: string, shotId: string, renderId: string): Promise<SelectRenderResponse> {
    return client
      .post(`/projects/${projectId}/shots/${shotId}/renders/${renderId}/select`)
      .then((r) => r.data as SelectRenderResponse);
  },
  lock(projectId: string, shotId: string): Promise<LockShotResponse> {
    return client
      .post(`/projects/${projectId}/shots/${shotId}/lock`)
      .then((r) => r.data as LockShotResponse);
  }
};
```

- [ ] **Step 4: 跑 API 测试**

```bash
cd frontend
npm run test -- shots.api.spec.ts
```

预期：通过。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/shots.ts frontend/tests/unit/shots.api.spec.ts
git commit -m "feat(frontend): add m3b shots api client  (Task M3b-FE-2)"
```

## Task 3: Workbench Store — render draft、确认生成、历史版本与恢复逻辑

**Files:**
- Modify: `frontend/src/store/workbench.ts`
- Test: `frontend/tests/unit/workbench.m3b.store.spec.ts`

- [ ] **Step 1: 写 failing store tests**

创建 `frontend/tests/unit/workbench.m3b.store.spec.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import { projectsApi } from "@/api/projects";
import { shotsApi } from "@/api/shots";

const mkProject = () => ({
  id: "P1",
  name: "Demo",
  stage: "场景已匹配",
  stage_raw: "scenes_locked",
  genre: null,
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
    description: "皇城夜景",
    detail: "",
    duration_sec: 3,
    tags: [],
    status: "succeeded",
    current_render_id: "R1",
    created_at: "2026-04-22T00:00:00Z",
    updated_at: "2026-04-22T00:00:00Z"
  }],
  characters: [],
  scenes: [],
  generationProgress: "",
  generationNotes: { input: "", suggestion: "" },
  generationQueue: [],
  exportConfig: [],
  exportDuration: "",
  exportTasks: []
});

describe("workbench M3b render actions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("fetchRenderDraft(): 缓存后端建议 prompt 与 references", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as any);
    vi.spyOn(shotsApi, "renderDraft").mockResolvedValue({
      shot_id: "SH1",
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{ id: "scene-1", kind: "scene", source_id: "scene01", name: "长安殿", image_url: "https://img", reason: "命中文案" }]
    } as any);
    const store = useWorkbenchStore();
    await store.load("P1");
    const draft = await store.fetchRenderDraft("SH1");
    expect(draft.prompt).toContain("图片1");
    expect(store.renderDraftFor("SH1")?.references).toHaveLength(1);
  });

  it("confirmRenderShot(): 写入 activeRenderJobId 与 activeRenderShotId", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as any);
    vi.spyOn(shotsApi, "render").mockResolvedValue({ job_id: "RJ1", sub_job_ids: [] });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.confirmRenderShot("SH1", {
      prompt: "图片1中的宫门，图片2中的主角。",
      references: []
    });
    expect(jobId).toBe("RJ1");
    expect(store.activeRenderJobId).toBe("RJ1");
    expect(store.activeRenderShotId).toBe("SH1");
  });

  it("fetchRenderVersions(): 缓存版本历史", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as any);
    vi.spyOn(shotsApi, "listRenders").mockResolvedValue([
      { id: "R1", shot_id: "SH1", version_no: 1, status: "succeeded", prompt_snapshot: {}, image_url: "https://img", provider_task_id: null, error_code: null, error_msg: null, created_at: "2026-04-22T00:00:00Z", finished_at: null, is_current: true }
    ] as any);
    const store = useWorkbenchStore();
    await store.load("P1");
    const rows = await store.fetchRenderVersions("SH1");
    expect(rows).toHaveLength(1);
    expect(store.renderVersionsFor("SH1")[0].id).toBe("R1");
  });
});
```

- [ ] **Step 2: 运行测试确认当前失败**

```bash
cd frontend
npm run test -- workbench.m3b.store.spec.ts
```

预期：失败，提示 `shotsApi` / render store 字段不存在。

- [ ] **Step 3: 在 store 中加入 render 追踪与 history cache**

更新 `frontend/src/store/workbench.ts`，新增 import：

```ts
import { shotsApi } from "@/api/shots";
import type { RenderDraftRead, RenderSubmitRequest, RenderVersionRead } from "@/types/api";
import type { RenderShotItem } from "@/types";
```

新增状态与选择器：

```ts
const renderJob = ref<{ projectId: string; jobId: string; shotId: string } | null>(null);
const renderError = ref<string | null>(null);
const renderDrafts = ref<Record<string, RenderDraftRead>>({});
const renderVersions = ref<Record<string, RenderVersionRead[]>>({});
const renderHistoryLoadingShotId = ref<string | null>(null);

const activeRenderJobId = computed<string | null>(() =>
  current.value && renderJob.value && renderJob.value.projectId === current.value.id
    ? renderJob.value.jobId
    : null
);
const activeRenderShotId = computed<string | null>(() =>
  current.value && renderJob.value && renderJob.value.projectId === current.value.id
    ? renderJob.value.shotId
    : null
);
```

新增动作：

```ts
async function fetchRenderDraft(shotId: string): Promise<RenderDraftRead> {
  if (!current.value) throw new Error("fetchRenderDraft: no current project");
  const draft = await shotsApi.renderDraft(current.value.id, shotId);
  renderDrafts.value[shotId] = draft;
  return draft;
}

function renderDraftFor(shotId: string): RenderDraftRead | null {
  return renderDrafts.value[shotId] ?? null;
}

function updateRenderDraft(
  shotId: string,
  patch: Partial<RenderDraftRead>,
) {
  const currentDraft = renderDrafts.value[shotId];
  if (!currentDraft) return;
  renderDrafts.value[shotId] = { ...currentDraft, ...patch };
}

async function confirmRenderShot(shotId: string, payload: RenderSubmitRequest): Promise<string> {
  if (!current.value) throw new Error("renderShot: no current project");
  if (activeRenderJobId.value) throw new Error("已有镜头渲染任务进行中");
  renderError.value = null;
  const resp = await shotsApi.render(current.value.id, shotId, payload);
  renderJob.value = { projectId: current.value.id, jobId: resp.job_id, shotId };
  return resp.job_id;
}

async function fetchRenderVersions(shotId: string): Promise<RenderVersionRead[]> {
  if (!current.value) throw new Error("fetchRenderVersions: no current project");
  renderHistoryLoadingShotId.value = shotId;
  try {
    const rows = await shotsApi.listRenders(current.value.id, shotId);
    renderVersions.value[shotId] = rows;
    return rows;
  } finally {
    renderHistoryLoadingShotId.value = null;
  }
}

function renderVersionsFor(shotId: string): RenderVersionRead[] {
  return renderVersions.value[shotId] ?? [];
}

async function selectRenderVersion(shotId: string, renderId: string) {
  if (!current.value) throw new Error("selectRenderVersion: no current project");
  await shotsApi.selectRender(current.value.id, shotId, renderId);
  await reload();
  await fetchRenderVersions(shotId);
}

async function lockShot(shotId: string) {
  if (!current.value) throw new Error("lockShot: no current project");
  await shotsApi.lock(current.value.id, shotId);
  await reload();
}

function markRenderSucceeded() {
  renderJob.value = null;
  renderError.value = null;
}

function markRenderFailed(msg: string) {
  renderJob.value = null;
  renderError.value = msg;
}

// 在 load(id) 切换项目时清空 M3b 缓存，避免跨项目串历史版本/草稿
renderDrafts.value = {};
renderVersions.value = {};
```

新增 shot-centric 视图组合器：

```ts
const renderShots = computed<RenderShotItem[]>(() => {
  return (current.value?.storyboards ?? []).map((shot) => {
    const queue = (current.value?.generationQueue ?? []).find(
      (item) =>
        item.kind === "render_shot" &&
        (
          item.target_id === shot.id ||
          item.shot_id === shot.id ||
          item.render_id === shot.current_render_id
        )
    );
    const isActive = activeRenderShotId.value === shot.id;
    return {
      shotId: shot.id,
      title: `镜头 ${String(shot.idx).padStart(2, "0")}`,
      summary: shot.title,
      shotStatus: queue?.shot_status ?? shot.status,
      status:
        queue?.status ??
        (shot.status === "failed"
          ? "warning"
          : shot.status === "generating"
            ? "processing"
            : "success"),
      progress:
        (isActive ? renderJob.value?.progress : undefined) ??
        queue?.progress ??
        (shot.status === "failed" ? 0 : shot.status === "generating" ? 1 : 100),
      currentRenderId: shot.current_render_id,
      imageUrl: queue?.image_url ?? null,
      versionNo: queue?.version_no ?? null,
      activeJobId: isActive ? activeRenderJobId.value : null,
      errorCode: queue?.error_code ?? null,
      errorMsg: queue?.error_msg ?? (queue?.status === "warning" ? renderError.value : null)
    };
  });
});
```

扩展 `findAndTrackActiveJobs()`：**把下面分支加在现有 `else { ... }` 内部，复用同一个 `jobs / running / lastFailed` 闭包，不要加到外层作用域。**

```ts
if (stage === "scenes_locked" || stage === "rendering" || stage === "ready_for_export") {
  const rJob = running("render_shot");
  if (rJob) {
    const shotId =
      rJob.target_id ??
      ((rJob.payload as { shot_id?: string } | null)?.shot_id ?? "") ??
      "";
    renderJob.value = { projectId: current.value.id, jobId: rJob.id, shotId };
  } else {
    const failed = lastFailed("render_shot");
    if (failed) renderError.value = failed.error_msg;
  }
}
```

- [ ] **Step 4: 导出 store API**

确保 `return { ... }` 里新增导出：

```ts
fetchRenderDraft,
renderDraftFor,
updateRenderDraft,
confirmRenderShot,
fetchRenderVersions,
renderVersionsFor,
selectRenderVersion,
lockShot,
markRenderSucceeded,
markRenderFailed,
renderShots,
activeRenderJobId,
activeRenderShotId,
renderHistoryLoadingShotId,
renderError
```

- [ ] **Step 5: 跑 store 测试**

```bash
cd frontend
npm run test -- workbench.m3b.store.spec.ts
```

预期：通过。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store/workbench.ts frontend/tests/unit/workbench.m3b.store.spec.ts
git commit -m "feat(frontend): add m3b render store workflow  (Task M3b-FE-3)"
```

## Task 4: GenerationPanel 交互化 + 历史版本 Modal

**Files:**
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Create: `frontend/src/components/generation/RenderVersionHistory.vue`
- Create: `frontend/src/components/generation/RenderRetryBanner.vue`
- Test: `frontend/tests/unit/generation.panel.spec.ts`

- [ ] **Step 1: 写 failing panel tests**

创建 `frontend/tests/unit/generation.panel.spec.ts`:

```ts
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, it, expect, beforeEach, vi } from "vitest";
import GenerationPanel from "@/components/generation/GenerationPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

describe("GenerationPanel", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("stage not renderable 时, 不展示确认生成入口", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "P1",
      name: "Demo",
      stage: "角色已锁定",
      stage_raw: "characters_locked",
      genre: null,
      ratio: "9:16",
      suggestedShots: "",
      story: "",
      summary: "",
      parsedStats: [],
      setupParams: [],
      projectOverview: "",
      storyboards: [],
      characters: [],
      scenes: [],
      generationProgress: "",
      generationNotes: { input: "", suggestion: "" },
      generationQueue: [],
      exportConfig: [],
      exportDuration: "",
      exportTasks: []
    } as any;
    const wrapper = mount(GenerationPanel, { global: { plugins: [pinia] } });
    expect(wrapper.text()).toContain("资产锁定后可开始镜头渲染");
  });

  it("先生成草稿再确认生成", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    vi.spyOn(store, "fetchRenderDraft").mockResolvedValue({
      shot_id: "SH1",
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img/scene.png", reason: "命中文案" }]
    } as any);
    vi.spyOn(store, "confirmRenderShot").mockResolvedValue("RJ1");
    vi.spyOn(store, "fetchRenderVersions").mockResolvedValue([]);
    store.current = {
      id: "P1",
      name: "Demo",
      stage: "镜头生成中",
      stage_raw: "rendering",
      genre: null,
      ratio: "9:16",
      suggestedShots: "",
      story: "",
      summary: "",
      parsedStats: [],
      setupParams: [],
      projectOverview: "",
      storyboards: [{
        id: "SH1", idx: 1, title: "开场", description: "", detail: "", duration_sec: 3, tags: [], status: "succeeded", current_render_id: "R1", created_at: "", updated_at: ""
      }],
      characters: [],
      scenes: [],
      generationProgress: "",
      generationNotes: { input: "", suggestion: "" },
      generationQueue: [],
      exportConfig: [],
      exportDuration: "",
      exportTasks: []
    } as any;
    store.selectShot("SH1");
    const wrapper = mount(GenerationPanel, { global: { plugins: [pinia] } });
    await wrapper.find("[data-testid='render-draft-btn']").trigger("click");
    expect(store.fetchRenderDraft).toHaveBeenCalledWith("SH1");
    await wrapper.find("[data-testid='confirm-render-btn']").trigger("click");
    expect(store.confirmRenderShot).toHaveBeenCalledWith("SH1", expect.objectContaining({
      prompt: "图片1中的宫门，图片2中的主角。"
    }));
  });
});
```

- [ ] **Step 2: 运行测试确认当前 panel 不满足**

```bash
cd frontend
npm run test -- generation.panel.spec.ts
```

预期：失败，因为组件没有按钮、没有 render history 交互。

- [ ] **Step 3: 新建失败提示与历史版本组件**

创建 `frontend/src/components/generation/RenderRetryBanner.vue`:

```vue
<script setup lang="ts">
const props = defineProps<{
  shotStatus: string;
  errorCode?: string | null;
  errorMsg?: string | null;
}>();

const labelMap: Record<string, string> = {
  content_filter: "内容违规",
  rate_limit: "触发限流",
  timeout: "请求超时",
  server_error: "服务异常",
  volcano_error: "生成失败"
};
</script>

<template>
  <div v-if="props.shotStatus === 'failed'" class="retry-banner">
    <strong>{{ labelMap[props.errorCode ?? "volcano_error"] ?? "生成失败" }}</strong>
    <p>{{ props.errorMsg ?? "请调整镜头描述后重试" }}</p>
  </div>
</template>
```

创建 `frontend/src/components/generation/RenderVersionHistory.vue`:

```vue
<script setup lang="ts">
import Modal from "@/components/common/Modal.vue";
import type { RenderVersionRead } from "@/types/api";

defineProps<{
  open: boolean;
  loading: boolean;
  versions: RenderVersionRead[];
  selectingId: string | null;
}>();

const emit = defineEmits<{
  close: [];
  select: [renderId: string];
}>();
</script>

<template>
  <Modal :open="open" title="历史版本" @close="emit('close')">
    <div v-if="loading" class="empty-note">正在加载版本历史...</div>
    <div v-else-if="!versions.length" class="empty-note">当前镜头还没有历史版本</div>
    <div v-else class="version-list">
      <article v-for="item in versions" :key="item.id" class="version-card">
        <img v-if="item.image_url" :src="item.image_url" alt="" />
        <div class="meta">
          <strong>v{{ item.version_no }}</strong>
          <p>{{ item.status }}</p>
          <button
            type="button"
            class="ghost-btn"
            :disabled="item.is_current || selectingId === item.id || item.status !== 'succeeded'"
            @click="emit('select', item.id)"
          >
            {{ item.is_current ? "当前版本" : "切为当前" }}
          </button>
        </div>
      </article>
    </div>
  </Modal>
</template>
```

- [ ] **Step 4: 重写 GenerationPanel**

把 `frontend/src/components/generation/GenerationPanel.vue` 改成真实容器，核心脚本保留如下结构：

```vue
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import RenderVersionHistory from "@/components/generation/RenderVersionHistory.vue";
import RenderRetryBanner from "@/components/generation/RenderRetryBanner.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { isApiError, messageFor } from "@/utils/error";

const store = useWorkbenchStore();
const { current, currentShot, renderShots, activeRenderJobId, activeRenderShotId, renderError } = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const historyOpen = ref(false);
const selectingRenderId = ref<string | null>(null);
const draftLoading = ref(false);
const draftPrompt = ref("");
const draftReferences = ref<Array<{ id: string; kind: string; source_id: string; name: string; image_url: string; reason?: string }>>([]);

const selectedRenderShot = computed(() =>
  renderShots.value.find((item) => item.shotId === currentShot.value?.id) ?? renderShots.value[0] ?? null
);
const selectedVersions = computed(() =>
  selectedRenderShot.value ? store.renderVersionsFor(selectedRenderShot.value.shotId) : []
);
const currentVersion = computed(() =>
  selectedVersions.value.find((item) => item.is_current) ?? selectedVersions.value[0] ?? null
);
const promptSnapshotText = computed(() =>
  currentVersion.value?.prompt_snapshot
    ? JSON.stringify(currentVersion.value.prompt_snapshot, null, 2)
    : ""
);
const versionErrorCode = computed(() => currentVersion.value?.error_code ?? selectedRenderShot.value?.errorCode ?? null);
const versionErrorMsg = computed(() => currentVersion.value?.error_msg ?? selectedRenderShot.value?.errorMsg ?? null);

const { job: renderJob } = useJobPolling(activeRenderJobId, {
  onSuccess: async () => {
    store.markRenderSucceeded();
    await store.reload();
    if (selectedRenderShot.value) await store.fetchRenderVersions(selectedRenderShot.value.shotId);
  },
  onError: (job, err) => {
    store.markRenderFailed(
      job?.error_msg ??
      (isApiError(err) ? messageFor(err.code, err.message) : err instanceof Error ? err.message : "镜头渲染失败")
    );
  }
});

function syncDraftFromStore() {
  const shotId = selectedRenderShot.value?.shotId;
  if (!shotId) return;
  const draft = store.renderDraftFor(shotId);
  draftPrompt.value = draft?.prompt ?? "";
  draftReferences.value = [...(draft?.references ?? [])];
}

async function generateDraft() {
  if (!selectedRenderShot.value) return;
  try {
    draftLoading.value = true;
    await store.fetchRenderDraft(selectedRenderShot.value.shotId);
    syncDraftFromStore();
  } catch (err) {
    toast.error(isApiError(err) ? messageFor(err.code, err.message) : err instanceof Error ? err.message : "生成镜头草稿失败");
  } finally {
    draftLoading.value = false;
  }
}

async function openHistory() {
  if (!selectedRenderShot.value) return;
  historyOpen.value = true;
  try {
    await store.fetchRenderVersions(selectedRenderShot.value.shotId);
  } catch (err) {
    toast.error(isApiError(err) ? messageFor(err.code, err.message) : err instanceof Error ? err.message : "加载历史版本失败");
  }
}

function removeReference(id: string) {
  draftReferences.value = draftReferences.value.filter((item) => item.id !== id);
}

async function confirmRender() {
  if (!selectedRenderShot.value) return;
  try {
    await store.confirmRenderShot(selectedRenderShot.value.shotId, {
      prompt: draftPrompt.value,
      references: draftReferences.value.map(({ id, kind, source_id, name, image_url }) => ({
        id,
        kind,
        source_id,
        name,
        image_url
      }))
    });
  } catch (err) {
    toast.error(isApiError(err) ? messageFor(err.code, err.message) : err instanceof Error ? err.message : "镜头渲染失败");
  }
}
```

模板上至少包含这些交互点：

- 左侧 shot 列表：点击切换 `store.selectShot(item.shotId)`
- `data-testid="render-draft-btn"` 的“生成草稿”按钮；只在 `flags.canRender` 时启用
- prompt `<textarea v-model="draftPrompt">`
- 参考图列表，支持删除单张引用 `removeReference(id)`；未要求在 M3b 做拖拽排序
- `data-testid="confirm-render-btn"` 的“确认生成”按钮；提交 `draftPrompt + draftReferences`
- 当 `activeRenderJobId` 已存在且 `activeRenderShotId !== selectedRenderShot?.shotId` 时，草稿按钮和确认生成按钮都要禁用，避免只靠 store 抛错
- “查看历史版本”按钮
- `RenderRetryBanner`，参数从 `versionErrorCode / versionErrorMsg / selectedRenderShot.shotStatus` 传入
- 右侧真实 `<img :src="selectedRenderShot.imageUrl">` 预览；无图时显示 empty note
- 进度条：仅当 `activeRenderShotId === selectedRenderShot.shotId && renderJob` 时显示
- “锁定最终版”按钮：调用 `store.lockShot(selectedRenderShot.shotId)`，并受 `flags.canLockShot` 门控
- notes 区用 `<pre>{{ promptSnapshotText }}</pre>` 展示 `promptSnapshotText`；不要直接渲染对象，避免出现 `[object Object]`
- `selectedRenderShot` 切换时，需要从 `store.renderDraftFor(shotId)` 同步本地临时表单；未生成过 draft 时展示 empty note

- [ ] **Step 5: 跑 panel 测试**

```bash
cd frontend
npm run test -- generation.panel.spec.ts
```

预期：通过。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/generation/GenerationPanel.vue frontend/src/components/generation/RenderRetryBanner.vue frontend/src/components/generation/RenderVersionHistory.vue frontend/tests/unit/generation.panel.spec.ts
git commit -m "feat(frontend): build m3b generation panel  (Task M3b-FE-4)"
```

## Task 5: SceneAssetsPanel 去掉手动绑定镜头入口

**Files:**
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Test: `frontend/tests/unit/scene.assets.panel.spec.ts`

- [ ] **Step 1: 写移除绑定按钮的用例**

创建 `frontend/tests/unit/scene.assets.panel.spec.ts`:

```ts
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, it, expect } from "vitest";
import SceneAssetsPanel from "@/components/scene/SceneAssetsPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

describe("SceneAssetsPanel", () => {
  it("M3b 不再展示绑定镜头入口", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "P1",
      name: "Demo",
      stage: "场景已锁定",
      stage_raw: "scenes_locked",
      storyboards: [{ id: "SH1", idx: 1, title: "开场", description: "", detail: "", duration_sec: 3, tags: [], status: "pending", current_render_id: null, created_at: "", updated_at: "" }],
      scenes: [{ id: "SC1", name: "长安殿", summary: "宫门", description: "宫门", reference_image_url: "https://img", locked: true, created_at: "", updated_at: "" }],
      characters: [],
      genre: null,
      ratio: "9:16",
      suggestedShots: "",
      story: "",
      summary: "",
      parsedStats: [],
      setupParams: [],
      projectOverview: "",
      generationProgress: "",
      generationNotes: { input: "", suggestion: "" },
      generationQueue: [],
      exportConfig: [],
      exportDuration: "",
      exportTasks: []
    } as any;
    const wrapper = mount(SceneAssetsPanel, { global: { plugins: [pinia] } });
    expect(wrapper.text()).not.toContain("绑定镜头");
  });
});
```

- [ ] **Step 2: 修改组件说明**

在 `frontend/src/components/scene/SceneAssetsPanel.vue` 中：

- 移除 `handleBind()`、`currentShot`、`canBind` 等只服务于手动绑定的逻辑
- 删除 “绑定镜头 XX → 此场景” 按钮
- 保留 “编辑描述 / 重新生成参考图 / 锁定场景”
- 右上角的“场景复用 X 镜头”统计可以继续保留为只读信息，但不再作为可点击操作入口

- [ ] **Step 3: 跑组件测试**

```bash
cd frontend
npm run test -- scene.assets.panel.spec.ts
```

预期：通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/scene/SceneAssetsPanel.vue frontend/tests/unit/scene.assets.panel.spec.ts
git commit -m "feat(frontend): remove manual shot scene binding entry  (Task M3b-FE-5)"
```

## Task 6: Workbench 恢复 in-flight render job

**Files:**
- Modify: `frontend/src/views/WorkbenchView.vue`
- Modify: `frontend/src/store/workbench.ts`
- Test: `frontend/tests/unit/workbench.m3b.store.spec.ts`

- [ ] **Step 1: 给恢复逻辑补用例**

在 `frontend/tests/unit/workbench.m3b.store.spec.ts` 追加：

```ts
it("findAndTrackActiveJobs(): 在 rendering 阶段接管 in-flight render_shot job", async () => {
  vi.spyOn(projectsApi, "get").mockResolvedValue({
    ...mkProject(),
    stage: "镜头生成中",
    stage_raw: "rendering"
  } as any);
  vi.spyOn(projectsApi, "getJobs").mockResolvedValue([
    {
      id: "RJ2",
      kind: "render_shot",
      status: "running",
      progress: 45,
      total: 100,
      done: 45,
      payload: { render_id: "R2" },
      result: null,
      error_msg: null,
      target_id: "SH1",
      created_at: "2026-04-22T00:00:00Z",
      finished_at: null
    } as any
  ]);
  const store = useWorkbenchStore();
  await store.load("P1");
  await store.findAndTrackActiveJobs();
  expect(store.activeRenderJobId).toBe("RJ2");
  expect(store.activeRenderShotId).toBe("SH1");
});
```

- [ ] **Step 2: 保持 WorkbenchView 入口不分叉**

`frontend/src/views/WorkbenchView.vue` 不要新增第二套恢复入口，只保留：

```ts
async function loadCurrent() {
  try {
    await store.load(String(route.params.id));
    await store.findAndTrackActiveJobs();
  } catch (e) {
    // 保持现有错误处理
  }
}
```

说明：`render_shot` 的恢复逻辑全部放在 `workbench.findAndTrackActiveJobs()`，不要在 view 里加 if/else 特判。

- [ ] **Step 3: 跑 store 测试**

```bash
cd frontend
npm run test -- workbench.m3b.store.spec.ts
```

预期：通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/store/workbench.ts frontend/src/views/WorkbenchView.vue frontend/tests/unit/workbench.m3b.store.spec.ts
git commit -m "feat(frontend): restore in-flight render jobs on reload  (Task M3b-FE-6)"
```

## Task 7: README 与 Smoke

**Files:**
- Create: `frontend/scripts/smoke_m3b.sh`
- Modify: `frontend/README.md`

- [ ] **Step 1: 新建 smoke 脚本**

创建 `frontend/scripts/smoke_m3b.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

API="${API:-http://127.0.0.1:8000/api/v1}"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "缺少 $1" >&2; exit 2; }
}
require curl
require jq

echo "[1/7] 需要一个已到 scenes_locked 的项目"
PID="${PID:-}"
if [[ -z "$PID" ]]; then
  echo "请先准备一个已有 scenes_locked 状态的 PID（可来自前置 M3a smoke）"
  exit 2
fi

SHOT_ID="$(curl -s "$API/projects/$PID" | jq -r '.data.storyboards[0].id')"
echo "[2/7] 先获取 render draft"
DRAFT="$(curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/render-draft")"
PROMPT="$(echo "$DRAFT" | jq -r '.data.prompt')"
REFS="$(echo "$DRAFT" | jq -c '.data.references | map({id,kind,source_id,name,image_url})')"

echo "[3/7] 确认并发起单镜头 render"
ACK="$(curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/render" \
  -H 'Content-Type: application/json' \
  -d "{\"prompt\":$(jq -Rn --arg v "$PROMPT" '$v'),\"references\":$REFS}")"
JOB_ID="$(echo "$ACK" | jq -r '.data.job_id')"
echo "job=$JOB_ID"

echo "[4/7] 轮询 job 直到成功"
SUCCEEDED=0
for i in {1..90}; do
  ST="$(curl -s "$API/jobs/$JOB_ID" | jq -r '.data.status')"
  echo "  render job status: $ST"
  if [[ "$ST" == "succeeded" ]]; then
    SUCCEEDED=1
    break
  fi
  [[ "$ST" == "failed" ]] && { echo "render 失败"; exit 1; }
  sleep 2
done

if [[ "$SUCCEEDED" != "1" ]]; then
  echo "render job timed out before success" >&2
  curl -s "$API/jobs/$JOB_ID" | jq .
  exit 1
fi

echo "[5/7] 校验 render history"
ROWS="$(curl -s "$API/projects/$PID/shots/$SHOT_ID/renders")"
RID="$(echo "$ROWS" | jq -r '.data[0].id')"
[[ -n "$RID" && "$RID" != "null" ]] || { echo "未返回 render history"; exit 1; }

echo "[6/7] 选择当前版本"
curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/renders/$RID/select" | jq .

echo "[7/7] 锁定最终版并校验 stage"
curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/lock" | jq .
curl -s "$API/projects/$PID" | jq '.data | {stage_raw,generationQueue}'
echo "SMOKE M3b OK — project=$PID shot=$SHOT_ID render=$RID"
```

- [ ] **Step 2: 更新 README**

在 `frontend/README.md` 增加一节：

```md
## M3b 单镜头渲染

M3b 前端新增：

- `src/api/shots.ts`
- `GenerationPanel` 先拿草稿、允许编辑 prompt / references、确认后生成
- `RenderVersionHistory` 历史版本切换
- 单镜头 `render_shot` job 轮询与刷新恢复
- 场景详情移除手动“绑定镜头 → 此场景”入口

联调前置：

1. 后端已合入 `docs/superpowers/plans/2026-04-22-backend-m3b-render-shot.md`
2. 项目已至少推进到 `scenes_locked`
3. 本地后端运行在 `127.0.0.1:8000`

冒烟：

```bash
cd frontend
chmod +x scripts/smoke_m3b.sh
PID=<已有 scenes_locked 项目 id> ./scripts/smoke_m3b.sh
```
```

- [ ] **Step 3: 跑前端测试 + smoke 前置检查**

```bash
cd frontend
npm run test -- shots.api.spec.ts workbench.m3b.store.spec.ts generation.panel.spec.ts useStageGate.spec.ts
npm run typecheck
```

预期：全部通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/scripts/smoke_m3b.sh frontend/README.md frontend/tests/unit/shots.api.spec.ts frontend/tests/unit/workbench.m3b.store.spec.ts frontend/tests/unit/generation.panel.spec.ts frontend/tests/unit/useStageGate.spec.ts
git commit -m "docs(frontend): add m3b render smoke and docs  (Task M3b-FE-7)"
```

## Self-Review Checklist

- Spec coverage:
  - `GenerationPanel` 真正可渲染、可查看历史版本、可切当前版本、可锁定最终版：Task 3 / Task 4
  - `GenerationPanel` 先请求 draft，再允许用户临时编辑 prompt / references，确认后才真正创建 render job：Task 3 / Task 4
  - 单镜头 render job 轮询：Task 3 / Task 4 / Task 6
  - 场景详情页没有遗留“绑定镜头 → 此场景”按钮：Task 5
  - 刷新后恢复 in-flight render job：Task 3 / Task 6
  - 与后端 `GenerateJobAck` / `generationQueue` job-based 契约一致：Task 0 / Task 1 / Task 3
  - `generationQueue[*]` 的 `render_shot` 项必须有 `target_id`；`GET /projects/{id}/jobs` 必须暴露 `target_id/payload/result/error_msg`，否则恢复逻辑直接 block：Task 0 / Task 3 / Task 6
  - smoke / README：Task 7
- `ProjectData.generationQueue` 仍是后端原始 job-based 结构，没有被前端类型误写成 shot-based 契约。
- M3b 前端明确只允许同项目一个 `render_shot` job 在跑，未偷偷引入并发调度。
- `GenerationPanel` 的 notes 区只展示当前版本 `prompt_snapshot`；没有历史版本时保持空态或展示当前 draft，不回退到全局 `generationNotes.input`。
- render draft 只保存在前端临时状态；刷新或离开页面后未确认草稿不恢复，不会误写入后端。
- 未越界实现 M3c 的批量继续生成 / 全量重渲 / 锁定全部最终版。

Plan complete and saved to `docs/superpowers/plans/2026-04-22-frontend-m3b-shot-rendering.md`.
