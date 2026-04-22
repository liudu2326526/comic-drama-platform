# Frontend M3c: 批量渲染工作台 + 单镜头状态补齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有前端工作台基础上，交付 M3c 的镜头生成页：既能发起 `render_batch` 批量渲染、展示父子 job 聚合进度与失败子集，也把当前前端缺失的 M3b 单镜头真实状态补齐，让 `GenerationPanel` 从 demo 占位升级为真实的镜头渲染工作台。

**Architecture:** 前端继续遵循“HTTP 只拿 ack，状态以 `GET /projects/{id}` 聚合快照为准”的原则；但 M3c 需要补两层本地状态。第一层是单镜头本地状态：`render-draft`、编辑中的 prompt/references、版本历史缓存。第二层是批量任务状态：当前激活的 `render_batch` 父 job、其 `sub_job_ids`、队列视图以及失败镜头列表。`GenerationPanel` 不直接拼装原始 API 数据，而是由 `workbench` store 提供 shot-centric view model；UI 上将单镜头操作与批量操作合并在同一面板，保证“先补 M3b 缺口，再接 M3c 新能力”的实现顺序。

**Tech Stack:** Vue 3.5 `<script setup>` / TypeScript strict / Pinia / Axios / Vitest / @vue/test-utils / 现有 `useJobPolling` / 现有 `useStageGate`。

---

## References

- Frontend spec: `docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §9.1-§10, §15 M3b/M3c
- Backend M3c plan: `docs/superpowers/plans/2026-04-22-backend-m3c-batch-render.md`
- Current frontend baseline:
  - `frontend/src/store/workbench.ts`
  - `frontend/src/components/generation/GenerationPanel.vue`
  - `frontend/src/types/api.ts`
  - `frontend/src/types/index.ts`
  - `frontend/src/api/projects.ts`
  - `frontend/src/composables/useJobPolling.ts`

## Scope

**Includes:**

- 新增 `shotsApi.renderBatch()` 与 render draft / render / history / select / lock 对接
- `workbench` store 新增 render draft、render history、active render batch、恢复逻辑
- `GenerationPanel` 重写为真实工作台
- 新增批量队列、失败镜头 banner、版本历史组件
- 通过 `GET /projects/{id}` 与 `GET /projects/{id}/jobs` 恢复运行中的 `render_batch`
- `frontend/scripts/smoke_m3c.sh` 与 README 更新

**Excludes:**

- M4 导出面板的完整性校验和 409 缺失镜头跳转
- 新的设计系统或全量样式重构
- 离线草稿持久化到 `localStorage`

## Current Baseline Notes

- `GenerationPanel.vue` 目前只读 `current.generationQueue[0]`，没有任何真实写操作，也没有当前镜头的 draft/history 状态。
- `types/index.ts` 里的 `RenderQueueItem` 仍是 demo 时代的 `{ id, title, summary, status }`，和后端真实 `generationQueue` 已经脱节。
- `workbench.ts` 已经有 parse / 角色 / 场景任务追踪范式，适合复用到单镜头与批量渲染，不需要再建单独 jobs store。
- 当前 `projectsApi.getJobs()` 已暴露 `target_type/target_id`，但未包含 `parent_id`；M3c 前端依赖后端计划补上该字段。
- 当前 store 还没有 `loadRenderHistory/selectRenderVersion/lockShotRender`，而 panel 若要真正替代 demo 占位，必须把这几条单镜头动作一起补上。

## File Structure

**Create:**

```text
frontend/src/api/shots.ts
frontend/src/components/generation/RenderBatchBanner.vue
frontend/src/components/generation/RenderQueueList.vue
frontend/src/components/generation/RenderVersionHistory.vue
frontend/tests/unit/shots.api.spec.ts
frontend/tests/unit/workbench.m3c.store.spec.ts
frontend/tests/unit/generation.panel.spec.ts
frontend/scripts/smoke_m3c.sh
```

**Modify:**

```text
frontend/src/types/api.ts
frontend/src/types/index.ts
frontend/src/store/workbench.ts
frontend/src/components/generation/GenerationPanel.vue
frontend/src/composables/useStageGate.ts
frontend/tests/unit/useStageGate.spec.ts
frontend/README.md
```

## Task 0: Contract Gate - 先卡住后端 M3c 契约

**Files:**
- Verify: `docs/superpowers/plans/2026-04-22-backend-m3c-batch-render.md`
- Verify running backend API

- [ ] **Step 1: 确认批量端点与 jobs 字段都到位**

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/projects/<pid>/shots/render \
  -H 'Content-Type: application/json' \
  -d '{"shot_ids":null,"force_regenerate":false}' | jq .

curl -s http://127.0.0.1:8000/api/v1/projects/<pid>/jobs | jq '.data[0]'
curl -s http://127.0.0.1:8000/api/v1/projects/<pid> | jq '.data.generationQueue'
```

预期：

- `POST /shots/render` 返回 `{ job_id, sub_job_ids }`
- `/projects/{id}/jobs` 中存在 `parent_id`
- `generationQueue` 中 `render_batch` 项带 `failed_shot_ids/succeeded_shot_ids/pending_shot_ids`

- [ ] **Step 2: 缺任何一个字段就先阻塞前端实现**

若以下任一项不满足，不进入前端开发：

- `render_batch` ack 不是 `GenerateJobAck`
- jobs API 缺 `parent_id`
- 聚合里的 `render_batch` 缺失败/成功/待完成镜头列表

## Task 1: Render API 与类型系统对齐

**Files:**
- Create: `frontend/src/api/shots.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`
- Test: `frontend/tests/unit/shots.api.spec.ts`

- [ ] **Step 1: 先写 API client 的 failing 测试**

创建 `frontend/tests/unit/shots.api.spec.ts`：

```ts
import { describe, expect, it, vi } from "vitest";
import { client } from "@/api/client";
import { shotsApi } from "@/api/shots";

vi.mock("@/api/client", () => ({
  client: {
    post: vi.fn(),
    get: vi.fn()
  }
}));

it("renderBatch posts the m3c payload shape", async () => {
  vi.mocked(client.post).mockResolvedValue({ data: { job_id: "job1", sub_job_ids: ["c1"] } });
  await shotsApi.renderBatch("p1", { shot_ids: null, force_regenerate: false });
  expect(client.post).toHaveBeenCalledWith("/projects/p1/shots/render", {
    shot_ids: null,
    force_regenerate: false
  });
});
```

- [ ] **Step 2: 运行测试确认 `shotsApi` 尚不存在**

Run:

```bash
cd frontend
npm run test -- shots.api.spec.ts
```

Expected: FAIL with module not found。

- [ ] **Step 3: 在 `types/api.ts` 扩展批量与 render 历史契约**

追加：

```ts
export interface RenderBatchRequest {
  shot_ids: string[] | null;
  force_regenerate: boolean;
}

export interface RenderBatchQueueState {
  id: string;
  kind: "render_batch";
  status: JobStatus;
  progress: number;
  done: number;
  total: number | null;
  failed_shot_ids: string[];
  succeeded_shot_ids: string[];
  pending_shot_ids: string[];
}
```

并把 `JobState` 扩展为：

```ts
export interface JobState {
  id: string;
  kind: string;
  parent_id?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  status: JobStatus;
  progress: number;
  total: number | null;
  done: number;
  payload: unknown | null;
  result: unknown | null;
  error_msg: string | null;
  created_at: string;
  finished_at: string | null;
}
```

- [ ] **Step 4: 在 `types/index.ts` 把 demo queue 类型替换成真实聚合类型**

更新：

```ts
export interface RenderQueueItem {
  id: string;
  kind: string;
  status: string;
  progress: number;
  target_id?: string | null;
  parent_id?: string | null;
  render_id?: string | null;
  shot_status?: string | null;
  failed_shot_ids?: string[];
  succeeded_shot_ids?: string[];
  pending_shot_ids?: string[];
}
```

- [ ] **Step 5: 新建 `shotsApi`**

创建 `frontend/src/api/shots.ts`：

```ts
import { client } from "./client";
import type {
  GenerateJobAck,
  RenderBatchRequest,
  RenderDraftRead,
  RenderSubmitRequest,
  RenderVersionRead
} from "@/types/api";

export const shotsApi = {
  renderBatch(projectId: string, body: RenderBatchRequest): Promise<GenerateJobAck> {
    return client.post(`/projects/${projectId}/shots/render`, body).then((r) => r.data as GenerateJobAck);
  },
  renderDraft(projectId: string, shotId: string): Promise<RenderDraftRead> {
    return client.post(`/projects/${projectId}/shots/${shotId}/render-draft`).then((r) => r.data as RenderDraftRead);
  },
  renderOne(projectId: string, shotId: string, body: RenderSubmitRequest): Promise<GenerateJobAck> {
    return client.post(`/projects/${projectId}/shots/${shotId}/render`, body).then((r) => r.data as GenerateJobAck);
  },
  listRenders(projectId: string, shotId: string): Promise<RenderVersionRead[]> {
    return client.get(`/projects/${projectId}/shots/${shotId}/renders`).then((r) => r.data as RenderVersionRead[]);
  },
  selectRender(projectId: string, shotId: string, renderId: string): Promise<{ shot_id: string; current_render_id: string; status: string }> {
    return client.post(`/projects/${projectId}/shots/${shotId}/renders/${renderId}/select`).then((r) => r.data as {
      shot_id: string;
      current_render_id: string;
      status: string;
    });
  },
  lockShot(projectId: string, shotId: string): Promise<{ shot_id: string; current_render_id: string; status: string }> {
    return client.post(`/projects/${projectId}/shots/${shotId}/lock`).then((r) => r.data as {
      shot_id: string;
      current_render_id: string;
      status: string;
    });
  }
};
```

- [ ] **Step 6: 跑测试**

Run:

```bash
cd frontend
npm run test -- shots.api.spec.ts
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add src/api/shots.ts src/types/api.ts src/types/index.ts tests/unit/shots.api.spec.ts
git commit -m "feat(frontend): add m3c shots api and render batch types"
```

## Task 2: `workbench` Store 补齐单镜头状态与批量任务追踪

**Files:**
- Modify: `frontend/src/store/workbench.ts`
- Test: `frontend/tests/unit/workbench.m3c.store.spec.ts`

- [ ] **Step 1: 先写 store 的 failing 测试**

创建 `frontend/tests/unit/workbench.m3c.store.spec.ts`：

```ts
it("tracks active render batch job and groups child render jobs by parent", async () => {
  const store = useWorkbenchStore();
  store.current = mockProjectWithQueue();

  mockProjectsApi.getJobs.mockResolvedValue([
    { id: "parent-1", kind: "render_batch", status: "running", progress: 50, parent_id: null, target_id: "p1" },
    { id: "child-1", kind: "render_shot", status: "running", parent_id: "parent-1", target_id: "s1" }
  ]);

  await store.findAndTrackActiveJobs();
  expect(store.activeRenderBatchJobId).toBe("parent-1");
  expect(store.renderChildJobIdsByParent["parent-1"]).toEqual(["child-1"]);
});
```

- [ ] **Step 2: 运行测试确认 store 尚未暴露这些状态**

Run:

```bash
cd frontend
npm run test -- workbench.m3c.store.spec.ts
```

Expected: FAIL with missing refs/selectors。

- [ ] **Step 3: 在 store 新增 render 相关状态**

在 `frontend/src/store/workbench.ts` 增加：

```ts
const renderDrafts = ref<Record<string, RenderDraftRead>>({});
const renderHistory = ref<Record<string, RenderVersionRead[]>>({});
const renderHistoryLoading = ref<Record<string, boolean>>({});
const renderBatchJob = ref<{ projectId: string; jobId: string } | null>(null);
const renderShotJobs = ref<Record<string, { projectId: string; jobId: string }>>({});

const activeRenderBatchJobId = computed(() => scopedJobId(renderBatchJob.value));
const latestBatchQueueItem = computed(() =>
  (current.value?.generationQueue ?? []).find((item) => item.kind === "render_batch") ?? null
);
const latestBatchFailedShotIds = computed(() => latestBatchQueueItem.value?.failed_shot_ids ?? []);
const latestBatchPendingShotIds = computed(() => latestBatchQueueItem.value?.pending_shot_ids ?? []);
const renderChildJobIdsByParent = computed<Record<string, string[]>>(() => {
  const out: Record<string, string[]> = {};
  const queue = current.value?.generationQueue ?? [];
  queue.filter((item) => item.kind === "render_shot" && item.parent_id).forEach((item) => {
    const parentId = item.parent_id as string;
    out[parentId] ??= [];
    out[parentId].push(item.id);
  });
  return out;
});
```

- [ ] **Step 4: 扩展 `findAndTrackActiveJobs()` 恢复 render jobs**

在 `findAndTrackActiveJobs()` 里追加：

```ts
if (stage === "scenes_locked" || stage === "rendering" || stage === "ready_for_export") {
  const batchJob = running("render_batch");
  if (batchJob) {
    renderBatchJob.value = { projectId: current.value.id, jobId: batchJob.id };
  }

  jobs
    .filter((j) => j.kind === "render_shot" && (j.status === "queued" || j.status === "running"))
    .forEach((j) => {
      if (j.target_id) {
        renderShotJobs.value[j.target_id] = { projectId: current.value!.id, jobId: j.id };
      }
    });
}
```

- [ ] **Step 5: 增加 render actions**

新增：

```ts
async function loadRenderDraft(shotId: string) {
  if (!current.value) throw new Error("loadRenderDraft: no current project");
  const draft = await shotsApi.renderDraft(current.value.id, shotId);
  renderDrafts.value[shotId] = draft;
  return draft;
}

async function loadRenderHistory(shotId: string) {
  if (!current.value) throw new Error("loadRenderHistory: no current project");
  renderHistoryLoading.value[shotId] = true;
  try {
    const versions = await shotsApi.listRenders(current.value.id, shotId);
    renderHistory.value[shotId] = versions;
    return versions;
  } finally {
    renderHistoryLoading.value[shotId] = false;
  }
}

async function startRenderBatch(payload: RenderBatchRequest) {
  if (!current.value) throw new Error("startRenderBatch: no current project");
  const ack = await shotsApi.renderBatch(current.value.id, payload);
  renderBatchJob.value = { projectId: current.value.id, jobId: ack.job_id };
  return ack;
}

async function selectRenderVersion(shotId: string, renderId: string) {
  if (!current.value) throw new Error("selectRenderVersion: no current project");
  await shotsApi.selectRender(current.value.id, shotId, renderId);
  await reload();
  await loadRenderHistory(shotId);
}

async function lockShotRender(shotId: string) {
  if (!current.value) throw new Error("lockShotRender: no current project");
  await shotsApi.lockShot(current.value.id, shotId);
  await reload();
  await loadRenderHistory(shotId);
}
```

并把这些状态和 action 加进 store 的返回值；在现有 return object 末尾追加下面这些键：

```ts
renderHistory,
renderHistoryLoading,
activeRenderBatchJobId,
latestBatchFailedShotIds,
latestBatchPendingShotIds,
renderChildJobIdsByParent,
loadRenderDraft,
loadRenderHistory,
selectRenderVersion,
lockShotRender,
startRenderBatch,
continueBatchRender,
```

- [ ] **Step 6: 运行 store 测试**

Run:

```bash
cd frontend
npm run test -- workbench.m3c.store.spec.ts
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add src/store/workbench.ts tests/unit/workbench.m3c.store.spec.ts
git commit -m "feat(frontend): track render drafts and batch jobs in workbench store"
```

## Task 3: `GenerationPanel` 从占位态升级为真实镜头工作台

**Files:**
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Create: `frontend/src/components/generation/RenderBatchBanner.vue`
- Create: `frontend/src/components/generation/RenderQueueList.vue`
- Create: `frontend/src/components/generation/RenderVersionHistory.vue`
- Test: `frontend/tests/unit/generation.panel.spec.ts`

- [ ] **Step 1: 写 panel 的 failing 测试**

创建 `frontend/tests/unit/generation.panel.spec.ts`：

```ts
it("shows batch progress banner and failed shot count from generationQueue", () => {
  const store = createWorkbenchWithQueue({
    generationQueue: [
      {
        id: "parent-1",
        kind: "render_batch",
        status: "failed",
        progress: 100,
        failed_shot_ids: ["s2", "s3"],
        succeeded_shot_ids: ["s1"],
        pending_shot_ids: []
      }
    ]
  });

  const wrapper = mount(GenerationPanel, { global: buildMountOptions(store) });
  expect(wrapper.text()).toContain("2 个镜头失败");
  expect(wrapper.text()).toContain("批量继续生成");
});
```

- [ ] **Step 2: 运行测试确认当前 panel 仍是 demo 结构**

Run:

```bash
cd frontend
npm run test -- generation.panel.spec.ts
```

Expected: FAIL。

- [ ] **Step 3: 拆出批量 banner 与队列列表组件**

创建 `RenderBatchBanner.vue`：

```vue
<script setup lang="ts">
defineProps<{
  activeJobId: string | null;
  failedShotIds: string[];
  pendingShotIds: string[];
  progressText: string;
}>();
</script>

<template>
  <div class="batch-banner">
    <strong>批量渲染</strong>
    <p v-if="activeJobId">任务进行中 · {{ progressText }}</p>
    <p v-else-if="failedShotIds.length">上次批量任务有 {{ failedShotIds.length }} 个镜头失败</p>
    <p v-else>可从未完成镜头继续批量生成</p>
  </div>
</template>
```

- [ ] **Step 4: 重写 `GenerationPanel.vue` 的主结构**

改成：

```vue
<template>
  <PanelSection v-if="current" kicker="05" title="镜头生成">
    <template #actions>
      <button class="primary-btn" type="button" :disabled="!canRender" @click="handleBatchRender">
        批量继续生成
      </button>
    </template>

    <RenderBatchBanner
      :active-job-id="activeRenderBatchJobId"
      :failed-shot-ids="latestBatchFailedShotIds"
      :pending-shot-ids="latestBatchPendingShotIds"
      :progress-text="current.generationProgress"
    />

    <div class="generation-layout">
      <RenderQueueList
        :shots="current.storyboards"
        :selected-shot-id="selectedShotId"
        :generation-queue="current.generationQueue"
        @select-shot="store.selectShot"
      />
      <div class="generation-preview">
        <RenderVersionHistory
          :versions="renderHistoryByShot[currentShot?.id ?? ''] ?? []"
          :loading="store.renderHistoryLoading[currentShot?.id ?? ''] ?? false"
          @refresh="loadHistory"
        />
      </div>
    </div>
  </PanelSection>
</template>
```

- [ ] **Step 5: 为当前镜头补草稿与版本历史读取**

在 `GenerationPanel.vue` 的 `<script setup>` 中接入：

```ts
const { current, selectedShotId, currentShot, activeRenderBatchJobId } = storeToRefs(store);
const renderHistoryByShot = computed(() => store.renderHistory);
const latestBatchFailedShotIds = computed(() => store.latestBatchFailedShotIds);
const latestBatchPendingShotIds = computed(() => store.latestBatchPendingShotIds);

async function handleBatchRender() {
  await store.continueBatchRender();
}

async function loadHistory() {
  if (!currentShot.value?.id) return;
  await store.loadRenderHistory(currentShot.value.id);
}

watch(
  () => currentShot.value?.id,
  async (shotId) => {
    if (!shotId) return;
    await store.loadRenderDraft(shotId);
    await store.loadRenderHistory(shotId);
  },
  { immediate: true }
);
```

并把模板里的历史版本和 loading 源改成 store 真正暴露的状态：

```vue
<RenderVersionHistory
  :versions="renderHistoryByShot[currentShot?.id ?? ''] ?? []"
  :loading="store.renderHistoryLoading[currentShot?.id ?? ''] ?? false"
  @refresh="loadHistory"
/>
```

- [ ] **Step 6: 运行 panel 测试**

Run:

```bash
cd frontend
npm run test -- generation.panel.spec.ts
```

Expected: PASS，后续样式与交互测试再补。

- [ ] **Step 7: Commit**

```bash
git add src/components/generation/GenerationPanel.vue src/components/generation/RenderBatchBanner.vue src/components/generation/RenderQueueList.vue src/components/generation/RenderVersionHistory.vue tests/unit/generation.panel.spec.ts
git commit -m "feat(frontend): build m3c generation workbench ui"
```

## Task 4: 阶段门、恢复提示与批量继续生成交互

**Files:**
- Modify: `frontend/src/composables/useStageGate.ts`
- Modify: `frontend/tests/unit/useStageGate.spec.ts`
- Modify: `frontend/src/store/workbench.ts`

- [ ] **Step 1: 写阶段门覆盖测试**

在 `frontend/tests/unit/useStageGate.spec.ts` 追加：

```ts
it("allows batch render during scenes_locked and rendering only", () => {
  expect(gateFlags("scenes_locked").canRender).toBe(true);
  expect(gateFlags("rendering").canRender).toBe(true);
  expect(gateFlags("ready_for_export").canRender).toBe(false);
});
```

- [ ] **Step 2: 运行测试确认当前语义是否与 M3c 一致**

Run:

```bash
cd frontend
npm run test -- useStageGate.spec.ts
```

Expected: 若失败则补 gate；若已通过，也保留测试作为防回归。

- [ ] **Step 3: 在 store 中增加“批量继续生成未完成镜头”派生**

在 `workbench.ts` 增加：

```ts
const unrenderedShotIds = computed(() =>
  (current.value?.storyboards ?? [])
    .filter((shot) => !["succeeded", "locked"].includes(shot.status))
    .map((shot) => shot.id)
);

async function continueBatchRender() {
  return startRenderBatch({ shot_ids: null, force_regenerate: false });
}
```

- [ ] **Step 4: 对运行中批量任务显示恢复提示**

在 panel 逻辑中，当 `activeRenderBatchJobId` 存在时显示：

```ts
const batchRecoveryHint = computed(() =>
  activeRenderBatchJobId.value ? "页面刷新后已恢复当前批量任务跟踪" : ""
);
```

并把它真正渲染到 `RenderBatchBanner` 下方：

```vue
<p v-if="batchRecoveryHint" class="recovery-hint">{{ batchRecoveryHint }}</p>
```

- [ ] **Step 5: 跑组合测试**

Run:

```bash
cd frontend
npm run test -- useStageGate.spec.ts workbench.m3c.store.spec.ts generation.panel.spec.ts
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add src/composables/useStageGate.ts tests/unit/useStageGate.spec.ts src/store/workbench.ts
git commit -m "feat(frontend): add m3c batch render gating and recovery cues"
```

## Task 5: Smoke、README 与联调说明

**Files:**
- Create: `frontend/scripts/smoke_m3c.sh`
- Modify: `frontend/README.md`

- [ ] **Step 1: 写 smoke 脚本**

创建 `frontend/scripts/smoke_m3c.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:5173}"
PROJECT_ID="${1:?project_id required}"

echo "Open ${APP_URL}/projects/${PROJECT_ID}"
echo "Manual smoke checklist:"
echo "1. GenerationPanel 能显示真实镜头列表"
echo "2. 点击“批量继续生成”后出现 batch banner"
echo "3. 刷新页面后仍能看到运行中的 batch job"
echo "4. 失败镜头数与 generationQueue 一致"
```

- [ ] **Step 2: 在 README 追加 M3c 范围说明**

更新 `frontend/README.md`：

```md
## M3c 范围

M3c 在前端交付：

- `render_batch` 批量继续生成
- 父子 job 聚合展示
- GenerationPanel 从占位态升级为真实镜头工作台
- 页面刷新后的批量任务恢复提示
```

- [ ] **Step 3: 跑本阶段验证**

Run:

```bash
cd frontend
npm run test -- shots.api.spec.ts workbench.m3c.store.spec.ts generation.panel.spec.ts useStageGate.spec.ts
npm run typecheck
```

Expected:

```text
Test Files 4 passed
Found 0 errors
```

- [ ] **Step 4: Commit**

```bash
git add README.md scripts/smoke_m3c.sh
git commit -m "docs(frontend): document m3c batch render workbench"
```

## Self-Review

- Spec coverage: 覆盖了 M3c 的批量渲染 UI、job 恢复提示，并明确把当前 M3b 前端缺口当作前置任务补齐。
- Placeholder scan: 任务、文件、命令与关键代码均明确，没有留空白描述。
- Type consistency: 全程统一 `renderBatch` / `activeRenderBatchJobId` / `failed_shot_ids` / `parent_id` 命名，与后端计划一致。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-22-frontend-m3c-batch-render-workbench.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
