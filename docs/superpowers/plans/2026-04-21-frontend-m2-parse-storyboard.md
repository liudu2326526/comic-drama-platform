# Frontend M2: 接入 /parse + 分镜 CRUD + useJobPolling 真实挂载 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M1 已交付的前端骨架之上,对接后端 M2 提供的 `POST /projects/{id}/parse`、`GET /jobs/{id}` 与 `/projects/{id}/storyboards/*` 六个端点,打通"创建项目 → 触发解析 → 轮询 job → 渲染分镜 → 编辑/重排/确认分镜"的完整 M2 工作流。`useJobPolling` 从空壳切换为真实挂载;`ProjectSetupPanel` 与 `StoryboardPanel` 从只读升级为可交互;阶段门严格对齐后端 `storyboard_editable` 编辑窗口。

**Architecture:** 继续遵守前端 spec §3 的分层(`api/` 纯请求、`store/` 写状态、`views/` 只编排、`components/` 按业务域分组)。M2 所有写路径统一策略:**写操作成功后 `await workbench.reload()`**,由后端聚合接口 `GET /projects/{id}` 一次性给出 `storyboards` + `generationQueue` + `generationProgress` 的一致态;前端不在本地做增删改的乐观合并,避免与后端 idx/status/stage 分叉。仅 `/parse` 触发的 job 走 `useJobPolling` 异步刷新(job 终态 → reload)。

**Tech Stack:** 沿用 M1(Vue 3.5 `<script setup>` / TS 5.7 strict / Vite 6 / Pinia 2 / Axios 1.x / Vitest 2 + @vue/test-utils);不新增运行时依赖。

**References:**
- 前端设计文档:`docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §6.3 / §7.2 / §7.3.1 / §7.3.2 / §7.3.7 / §8 / §15 M2
- 后端设计文档:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §5.1(编辑窗口)/§6.2(端点)/§13.1(字段映射)/§14(错误码)
- Backend M2 plan(契约来源):`docs/superpowers/plans/2026-04-21-backend-m2-pipeline-and-mock.md` Task 9(jobs)/ Task 10(storyboards)/ Task 11(parse)/ Task 12(聚合详情)
- Frontend M1 plan(已交付的骨架):`docs/superpowers/plans/2026-04-21-frontend-m1-skeleton.md`
- 视觉参考源:`product/workbench-demo/`(M2 仍不做视觉再设计,复用 demo 类名与配色变量)

---

## M2 范围与非范围(对齐前端 spec §15)

### 本里程碑交付

- `api/storyboards.ts` 与后端 `/projects/{id}/storyboards` 六端点 1:1,函数签名严格按后端 schema
- `api/projects.ts` 增加 `parse(id)`,返回 `{ job_id }`
- `types/api.ts` 增加 `StoryboardDetail` / `StoryboardCreateRequest` / `StoryboardUpdateRequest` / `StoryboardReorderRequest` / `StoryboardReorderResponse` / `StoryboardConfirmResponse` / `ProjectParseResponse`
- `store/workbench.ts` 新增 `activeParseJobId` / `startParse()` / `confirmStoryboards()` / 分镜写操作薄包装(调 api 后 `reload()`)
- `ProjectCreateView` 双按钮(**保存草稿** / **开始拆分分镜**),后者走 create → parse → 跳转 workbench 并自动轮询
- `ProjectSetupPanel` 新增 "开始拆分分镜" 大按钮(`stage === draft && storyboards.length === 0`);job 运行时显示进度条;失败显示错误 banner
- `StoryboardPanel` 全面可交互:新增 / 编辑 / 删除 / 上移 / 下移 / 确认 N 个镜头,严格按 `useStageGate.canEditStoryboards` 控制写按钮
- 新组件 `StoryboardEditorModal.vue`:新增 / 编辑分镜的表单弹窗
- `useJobPolling` 真实挂载到 setup panel(M1 只测过逻辑,M2 起真正驱动 UI)
- 阶段门拦截:在不允许编辑的 stage 上点写按钮 → toast + 打开 `StageRollbackModal`
- Vitest 覆盖 `api/storyboards` 请求拼装 + `workbench.startParse` / `confirmStoryboards` 动作逻辑
- `scripts/smoke_m2.sh` 冒烟脚本:启动前端 + 后端,走 create → parse → 轮询 → 列分镜 → reorder → confirm 全链路,最后校验 `stage_raw=storyboard_ready`
- README 新增 "M2 范围" 一节,列命令与端点

### 非范围(M3a+ 再做)

- 角色 / 场景 / 镜头渲染 / 导出相关 UI 与 API(对应 `/characters/*` / `/scenes/*` / `/shots/*` / `/exports` 端点)
- 单个 shot 的"生成角色参考图"按钮与 job
- 分镜拖拽排序(M2 用"上移/下移"按钮,拖拽 M3a+)
- 分镜批量操作(批量删 / 批量改时长)
- 版本历史 / 回退到历史分镜版本
- i18n / 多人协作 / 登录鉴权

---

## 文件结构(M2 交付的所有文件)

**新建**:

```
frontend/
├── scripts/
│   └── smoke_m2.sh                             # M2 新增冒烟
└── src/
    ├── api/
    │   └── storyboards.ts                      # 新增:六端点客户端
    └── components/
        └── storyboard/
            └── StoryboardEditorModal.vue       # 新增:新增/编辑表单弹窗

tests/unit/
├── storyboards.api.spec.ts                     # 新增:mock client 测请求拼装
└── workbench.store.spec.ts                     # 新增:startParse/confirmStoryboards 动作
```

**修改**:

```
frontend/
├── README.md                                   # 新增"M2 范围"一节
└── src/
    ├── api/
    │   └── projects.ts                         # 增加 parse(id)
    ├── types/
    │   └── api.ts                              # 新增 Storyboard* / ProjectParseResponse 类型
    ├── store/
    │   └── workbench.ts                        # 新增 startParse/confirmStoryboards/shot 写动作
    ├── views/
    │   ├── ProjectCreateView.vue               # 双按钮:保存草稿/开始拆分分镜
    │   └── WorkbenchView.vue                   # 监听 activeParseJobId 触发 reload
    └── components/
        ├── setup/
        │   └── ProjectSetupPanel.vue           # 空态按钮 + 进度条 + job 失败 banner
        └── storyboard/
            └── StoryboardPanel.vue             # 全面可交互
```

---

## 实施前提

- 已在 `feat/frontend-m2` 或类似分支;M1 已 merge 到当前分支
- 本地已能执行 `cd frontend && pnpm install`
- 后端 M2 已交付并跑通 `./backend/scripts/smoke_m2.sh`(parse + storyboards 端点可用,`CELERY_TASK_ALWAYS_EAGER=true` 下一次 HTTP 请求内走完 parse 链)
- 环境变量 `VITE_API_BASE_URL=/api/v1`(vite dev server 已通过 `server.proxy["/api"] = "http://127.0.0.1:8000"`);M2 新端点 `/parse` / `/jobs/*` / `/storyboards/*` 均在 `/api/v1/*` 前缀下,被现有 proxy 规则直接覆盖,**本 plan 不改 `vite.config.ts`**

---

## Task 1: 类型扩充 + `api/storyboards.ts` + `api/projects.ts.parse()`

**Files:**
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/api/storyboards.ts`
- Modify: `frontend/src/api/projects.ts`

- [ ] **Step 1: 在 `types/api.ts` 末尾追加 M2 类型**

```ts
// ---- M2: storyboards / parse ----
export interface StoryboardDetail {
  id: string;
  idx: number;
  title: string;
  description: string;
  detail: string | null;
  duration_sec: number | null;
  tags: string[] | null;
  status: string;                     // pending|generating|succeeded|failed|locked
  scene_id: string | null;
  current_render_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryboardCreateRequest {
  title?: string;                     // ≤ 128
  description?: string;
  detail?: string | null;
  duration_sec?: number | null;       // 0 ≤ x ≤ 300
  tags?: string[] | null;
  idx?: number | null;                // 1..999;null/缺省 = 追加到尾
}

export interface StoryboardUpdateRequest {
  title?: string;                     // ≤ 128;显式 null 会被后端 422
  description?: string;
  detail?: string | null;             // 显式 null 允许(清空)
  duration_sec?: number;
  tags?: string[];
}

export interface StoryboardReorderRequest {
  ordered_ids: string[];              // 必须正好包含当前项目下全部分镜 id
}

export interface StoryboardReorderResponse {
  reordered: number;
}

export interface StoryboardConfirmResponse {
  stage: ProjectStageRaw;
  stage_raw: ProjectStageRaw;
}

export interface StoryboardDeleteResponse {
  deleted: boolean;
}

export interface ProjectParseResponse {
  job_id: string;
}
```

- [ ] **Step 2: 创建 `frontend/src/api/storyboards.ts`**

```ts
/* frontend/src/api/storyboards.ts */
import { client } from "./client";
import type {
  StoryboardConfirmResponse,
  StoryboardCreateRequest,
  StoryboardDeleteResponse,
  StoryboardDetail,
  StoryboardReorderRequest,
  StoryboardReorderResponse,
  StoryboardUpdateRequest
} from "@/types/api";

export const storyboardsApi = {
  list(projectId: string): Promise<StoryboardDetail[]> {
    return client
      .get(`/projects/${projectId}/storyboards`)
      .then((r) => r.data as StoryboardDetail[]);
  },
  create(projectId: string, payload: StoryboardCreateRequest): Promise<StoryboardDetail> {
    return client
      .post(`/projects/${projectId}/storyboards`, payload)
      .then((r) => r.data as StoryboardDetail);
  },
  update(
    projectId: string,
    shotId: string,
    payload: StoryboardUpdateRequest
  ): Promise<StoryboardDetail> {
    return client
      .patch(`/projects/${projectId}/storyboards/${shotId}`, payload)
      .then((r) => r.data as StoryboardDetail);
  },
  remove(projectId: string, shotId: string): Promise<StoryboardDeleteResponse> {
    return client
      .delete(`/projects/${projectId}/storyboards/${shotId}`)
      .then((r) => r.data as StoryboardDeleteResponse);
  },
  reorder(
    projectId: string,
    payload: StoryboardReorderRequest
  ): Promise<StoryboardReorderResponse> {
    return client
      .post(`/projects/${projectId}/storyboards/reorder`, payload)
      .then((r) => r.data as StoryboardReorderResponse);
  },
  confirm(projectId: string): Promise<StoryboardConfirmResponse> {
    return client
      .post(`/projects/${projectId}/storyboards/confirm`)
      .then((r) => r.data as StoryboardConfirmResponse);
  }
};
```

- [ ] **Step 3: 在 `api/projects.ts` 追加 `parse`**

```ts
// 顶部 import 追加 ProjectParseResponse
import type {
  ProjectCreateRequest,
  ProjectCreateResponse,
  ProjectListResponse,
  ProjectParseResponse,
  ProjectRollbackRequest,
  ProjectRollbackResponse,
  ProjectUpdateRequest
} from "@/types/api";

// 在 projectsApi 对象末尾增加(注意逗号):
  parse(id: string): Promise<ProjectParseResponse> {
    // EAGER 模式后端会同步等 parse_novel + gen_storyboard 跑完,mock 足够快
    // 但接真实 LLM(M3a+)可能破 15s 默认超时。这里单独放宽到 60s。
    return client
      .post(`/projects/${id}/parse`, undefined, { timeout: 60_000 })
      .then((r) => r.data as ProjectParseResponse);
  }
```

最终 `projectsApi` 对象为:

```ts
export const projectsApi = {
  list(params?: { page?: number; page_size?: number }): Promise<ProjectListResponse> {
    return client.get("/projects", { params }).then((r) => r.data as ProjectListResponse);
  },
  create(payload: ProjectCreateRequest): Promise<ProjectCreateResponse> {
    return client.post("/projects", payload).then((r) => r.data as ProjectCreateResponse);
  },
  get(id: string): Promise<ProjectData> {
    return client.get(`/projects/${id}`).then((r) => r.data as ProjectData);
  },
  update(id: string, payload: ProjectUpdateRequest): Promise<ProjectData> {
    return client.patch(`/projects/${id}`, payload).then((r) => r.data as ProjectData);
  },
  remove(id: string): Promise<{ deleted: boolean }> {
    return client.delete(`/projects/${id}`).then((r) => r.data as { deleted: boolean });
  },
  rollback(id: string, payload: ProjectRollbackRequest): Promise<ProjectRollbackResponse> {
    return client.post(`/projects/${id}/rollback`, payload).then((r) => r.data as ProjectRollbackResponse);
  },
  parse(id: string): Promise<ProjectParseResponse> {
    // EAGER 模式后端会同步等 parse_novel + gen_storyboard 跑完,mock 足够快
    // 但接真实 LLM(M3a+)可能破 15s 默认超时。这里单独放宽到 60s。
    return client
      .post(`/projects/${id}/parse`, undefined, { timeout: 60_000 })
      .then((r) => r.data as ProjectParseResponse);
  }
};
```

- [ ] **Step 4: 跑 typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: 无错。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/storyboards.ts frontend/src/api/projects.ts
git commit -m "feat(frontend): api/storyboards 六端点 + api/projects.parse()"
```

---

## Task 2: `store/workbench.ts` 扩展 — parse job / confirm / shot 写动作

**Files:**
- Modify: `frontend/src/store/workbench.ts`

**契约决策**:所有 shot 写动作(create/update/delete/reorder/confirm)成功后**都调用 `reload()`**,以便从 `GET /projects/{id}` 拿到聚合字段(格式化的 `duration` 字符串、`generationQueue.status`、`generationProgress` 等)。不在前端做本地合并。

**Parse job 作用域决策**:`parseJob` 按 `projectId` 作用域,避免"A 项目 parse 中 → 切到 B 项目 → B 的 setup panel 对着 A 的 jobId 轮询"的串台。store 内部持有 `{ projectId, jobId }` 对;暴露给 UI 的 `activeParseJobId` 是 computed,当 `current.id !== parseJob.projectId` 时返回 null,让 `useJobPolling` 自动停轮。

- [ ] **Step 1: 全量替换 `frontend/src/store/workbench.ts`**

```ts
/* frontend/src/store/workbench.ts */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { projectsApi } from "@/api/projects";
import { storyboardsApi } from "@/api/storyboards";
import type { ProjectData } from "@/types";
import type {
  ProjectRollbackRequest,
  ProjectRollbackResponse,
  StoryboardConfirmResponse,
  StoryboardCreateRequest,
  StoryboardUpdateRequest
} from "@/types/api";

export type WorkflowStep = "setup" | "storyboard" | "character" | "scene" | "render" | "export";

export const useWorkbenchStore = defineStore("workbench", () => {
  const current = ref<ProjectData | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const selectedShotId = ref<string>("");
  const selectedCharacterId = ref<string>("");
  const selectedSceneId = ref<string>("");
  const activeStep = ref<WorkflowStep>("setup");

  // M2: parse job 追踪(按 projectId 作用域,避免跨项目串台)
  const parseJob = ref<{ projectId: string; jobId: string } | null>(null);
  const parseError = ref<string | null>(null);
  const activeParseJobId = computed<string | null>(() => {
    const pj = parseJob.value;
    if (!pj || !current.value || pj.projectId !== current.value.id) return null;
    return pj.jobId;
  });

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

  // ---- M2 动作 ----

  /** 触发后端 parse,把 job 信息写到 parseJob(含 projectId 作用域);UI 侧 useJobPolling 监听 activeParseJobId 并在终态 reload */
  async function startParse(projectId?: string): Promise<string> {
    const pid = projectId ?? current.value?.id;
    if (!pid) throw new Error("startParse: no project id");
    parseError.value = null;
    const resp = await projectsApi.parse(pid);
    parseJob.value = { projectId: pid, jobId: resp.job_id };
    return resp.job_id;
  }

  function markParseSucceeded() {
    parseJob.value = null;
    parseError.value = null;
  }
  function markParseFailed(msg: string) {
    parseJob.value = null;
    parseError.value = msg;
  }

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

  /** 上移一格:把 shot 与前一格交换。若已是第一格则 no-op。 */
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

  function selectShot(id: string) {
    selectedShotId.value = id;
  }
  function selectCharacter(id: string) {
    selectedCharacterId.value = id;
  }
  function selectScene(id: string) {
    selectedSceneId.value = id;
  }
  function setStep(step: WorkflowStep) {
    activeStep.value = step;
  }

  return {
    current,
    loading,
    error,
    selectedShotId,
    selectedCharacterId,
    selectedSceneId,
    activeStep,
    activeParseJobId,
    parseError,
    currentShot,
    selectedCharacter,
    selectedScene,
    load,
    reload,
    rollback,
    startParse,
    markParseSucceeded,
    markParseFailed,
    createShot,
    updateShot,
    deleteShot,
    reorderShots,
    moveShotUp,
    moveShotDown,
    confirmStoryboards,
    selectShot,
    selectCharacter,
    selectScene,
    setStep
  };
});
```

- [ ] **Step 2: typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: 无错。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/store/workbench.ts
git commit -m "feat(frontend): workbench store 新增 startParse/confirmStoryboards/shot CRUD 薄包装"
```

---

## Task 3: `ProjectCreateView` 双按钮改造(保存草稿 / 开始拆分分镜)

**Files:**
- Modify: `frontend/src/views/ProjectCreateView.vue`

**交互规则(前端 spec §7.2)**:
- **保存草稿**:走现有 M1 路径,创建后跳 workbench(仍 `stage=draft`)
- **开始拆分分镜**:创建项目成功后立刻调 `projectsApi.parse`,将 `job_id` 塞入 `workbench.activeParseJobId`,再跳 workbench;workbench 的 setup panel 会接管轮询
- `story.trim().length < 200` → 两个按钮都禁用并提示
- `story.trim().length > 5000` → 允许,但提示"文本较长,解析可能较慢"

- [ ] **Step 1: 全量替换 `frontend/src/views/ProjectCreateView.vue`**

```vue
<!-- frontend/src/views/ProjectCreateView.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import { useProjectsStore } from "@/store/projects";
import { useWorkbenchStore } from "@/store/workbench";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";

const form = ref({
  name: "",
  story: "",
  genre: "古风权谋",
  ratio: "9:16"
});
const savingDraft = ref(false);
const startingParse = ref(false);
const router = useRouter();
const toast = useToast();
const projects = useProjectsStore();
const workbench = useWorkbenchStore();

const storyLen = computed(() => form.value.story.trim().length);
const canSubmit = computed(() => form.value.name.trim().length > 0 && storyLen.value >= 200);
const isLongStory = computed(() => storyLen.value > 5000);

async function createOnly(): Promise<string | null> {
  const resp = await projects.createProject({
    name: form.value.name.trim(),
    story: form.value.story.trim(),
    genre: form.value.genre,
    ratio: form.value.ratio
  });
  return resp.id;
}

async function saveDraft() {
  if (!canSubmit.value || savingDraft.value) return;
  savingDraft.value = true;
  try {
    const id = await createOnly();
    if (!id) return;
    toast.success("项目草稿已保存");
    await router.push({ name: "workbench", params: { id } });
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "创建失败");
  } finally {
    savingDraft.value = false;
  }
}

async function startParse() {
  if (!canSubmit.value || startingParse.value) return;
  startingParse.value = true;
  let createdId: string | null = null;
  try {
    createdId = await createOnly();
    if (!createdId) return;
    await workbench.startParse(createdId);
    toast.success("已开始拆分分镜");
    await router.push({ name: "workbench", params: { id: createdId } });
  } catch (e) {
    // 如果项目已创建但 parse 失败,也跳到 workbench,让用户在 setup panel 重试
    if (createdId) {
      toast.warning(
        e instanceof ApiError ? messageFor(e.code, e.message) : "拆分未能启动,请在工作台重试"
      );
      await router.push({ name: "workbench", params: { id: createdId } });
    } else {
      toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "创建失败");
    }
  } finally {
    startingParse.value = false;
  }
}
</script>

<template>
  <div class="page-shell">
    <AppTopbar title="新建项目">
      <button class="ghost-btn" @click="$router.back()">返回</button>
    </AppTopbar>

    <form class="create-form" @submit.prevent>
      <label>
        <span>项目名</span>
        <input v-model="form.name" maxlength="128" placeholder="如:皇城夜雨" />
      </label>

      <div class="form-row">
        <label>
          <span>题材</span>
          <select v-model="form.genre">
            <option>古风权谋</option>
            <option>学院科幻</option>
            <option>都市悬疑</option>
            <option>其他</option>
          </select>
        </label>
        <label>
          <span>画幅比例</span>
          <select v-model="form.ratio">
            <option>9:16</option>
            <option>16:9</option>
            <option>1:1</option>
          </select>
        </label>
      </div>

      <label>
        <span>小说正文 ({{ storyLen }} 字, 需 ≥ 200 字)</span>
        <textarea v-model="form.story" rows="12" placeholder="粘贴完整小说正文..." />
      </label>

      <p v-if="isLongStory" class="hint">文本较长,解析可能较慢。</p>

      <footer>
        <button type="button" class="ghost-btn" @click="$router.back()">取消</button>
        <button
          type="button"
          class="ghost-btn"
          :disabled="!canSubmit || savingDraft || startingParse"
          @click="saveDraft"
        >
          {{ savingDraft ? "保存中..." : "保存草稿" }}
        </button>
        <button
          type="button"
          class="primary-btn"
          :disabled="!canSubmit || savingDraft || startingParse"
          @click="startParse"
        >
          {{ startingParse ? "启动中..." : "开始拆分分镜" }}
        </button>
      </footer>
    </form>
  </div>
</template>

<style scoped>
.create-form {
  max-width: 800px;
  margin: 24px auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: var(--panel-bg);
  padding: 32px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--panel-border);
}
.create-form label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.create-form input,
.create-form select,
.create-form textarea {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font: inherit;
}
.create-form footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}
.hint {
  font-size: 12px;
  color: var(--warning);
  margin: 0;
}
</style>
```

- [ ] **Step 2: 手测**

- 启动后端(CELERY_TASK_ALWAYS_EAGER=true)+ 前端
- 访问 `/projects/new`,正文 < 200 字 → 按钮禁用
- 填写 ≥ 200 字,点"保存草稿" → 跳 workbench,`stage=草稿中`,setup panel 显示"开始拆分分镜"大按钮(Task 4 交付)
- 回到创建页,点"开始拆分分镜" → 跳 workbench,setup panel 直接进入"正在解析…"态(Task 4 交付)

- [ ] **Step 3: typecheck + build**

Run: `cd frontend && pnpm typecheck && pnpm build`
Expected: 全部通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ProjectCreateView.vue
git commit -m "feat(frontend): ProjectCreateView 双按钮 — 保存草稿 / 开始拆分分镜"
```

---

## Task 4: `ProjectSetupPanel` 升级 — 空态按钮 + 轮询进度 + 错误 banner

**Files:**
- Modify: `frontend/src/components/setup/ProjectSetupPanel.vue`

**交互规则(前端 spec §7.3.1 + §10)**:

| 条件 | 展示 |
| --- | --- |
| `stage === draft` && `storyboards.length === 0` && 无活跃 parse job | 顶部大按钮 **开始拆分分镜** |
| `activeParseJobId` 非空 | 顶部进度条 + 文案 `正在解析小说… {progress}%`;M2 禁用大按钮 |
| `parseError` 非空 | 红色 banner:错误摘要 + `重试` 按钮(再次 startParse)|
| `stage !== draft` 或已有 storyboards | 不显示按钮;维持 M1 只读展示 |

- [ ] **Step 1: 全量替换 `frontend/src/components/setup/ProjectSetupPanel.vue`**

```vue
<!-- frontend/src/components/setup/ProjectSetupPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";

const store = useWorkbenchStore();
const { current, activeParseJobId, parseError } = storeToRefs(store);
const toast = useToast();

const startingParse = ref(false);

const canStartParse = computed(
  () =>
    current.value?.stage_raw === "draft" &&
    current.value.storyboards.length === 0 &&
    !activeParseJobId.value
);

// 注意:canStartParse 故意不排除 startingParse,让空态 CTA 在 POST /parse
// 进行中继续可见(按钮自身 :disabled="startingParse" + 文案切换),避免网络请求
// 窗口期整个 UI 空白。

// activeParseJobId 已是 storeToRefs 返回的 Ref<string | null>,直接传给 useJobPolling
const { job } = useJobPolling(activeParseJobId, {
  onProgress: () => {
    // 进度推进,UI 自动响应 job.value
  },
  onSuccess: async () => {
    try {
      await store.reload();
      store.markParseSucceeded();
      toast.success("分镜已生成");
    } catch (e) {
      store.markParseFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ?? (err instanceof ApiError ? messageFor(err.code, err.message) : "解析失败");
    store.markParseFailed(msg);
    toast.error(msg);
  }
});

async function triggerParse() {
  if (!current.value || startingParse.value) return;
  startingParse.value = true;
  try {
    await store.startParse(current.value.id);
  } catch (e) {
    const msg = e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败";
    store.markParseFailed(msg);
    toast.error(msg);
  } finally {
    startingParse.value = false;
  }
}

const progressLabel = computed(() => {
  const j = job.value;
  if (!j) return "正在排队…";
  if (j.total && j.total > 0) return `正在解析小说… ${j.done}/${j.total}`;
  return `正在解析小说… ${j.progress}%`;
});
</script>

<template>
  <PanelSection v-if="current" kicker="新建项目" :title="current.name">
    <template #actions>
      <span v-if="current.genre" class="tag warm">{{ current.genre }}</span>
      <span v-if="current.ratio" class="tag">{{ current.ratio }}</span>
      <span v-if="current.suggestedShots" class="tag">{{ current.suggestedShots }}</span>
    </template>

    <!-- 解析进行中 -->
    <div v-if="activeParseJobId" class="parse-banner running">
      <div class="parse-banner-head">
        <strong>{{ progressLabel }}</strong>
        <span v-if="job?.kind">job: {{ job.kind }}</span>
      </div>
      <ProgressBar :value="job?.progress ?? 0" />
    </div>

    <!-- 解析失败 -->
    <div v-else-if="parseError" class="parse-banner error">
      <div class="parse-banner-head">
        <strong>分镜解析失败</strong>
        <button class="ghost-btn small" @click="triggerParse">重试</button>
      </div>
      <p>{{ parseError }}</p>
    </div>

    <!-- 空态大按钮 -->
    <div v-else-if="canStartParse" class="empty-cta">
      <p>尚未生成分镜 · 点击下方按钮触发 AI 解析</p>
      <button class="primary-btn large" :disabled="startingParse" @click="triggerParse">
        {{ startingParse ? "启动中..." : "开始拆分分镜" }}
      </button>
    </div>

    <div class="project-setup">
      <div class="story-input-card">
        <label>小说内容输入</label>
        <textarea :value="current.story" readonly />
        <div v-if="current.parsedStats?.length" class="input-footer">
          <span v-for="stat in current.parsedStats" :key="stat">{{ stat }}</span>
        </div>
      </div>

      <div class="setup-side">
        <article v-if="current.setupParams?.length" class="mini-card">
          <span>项目参数</span>
          <ul>
            <li v-for="item in current.setupParams" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article v-if="current.summary" class="mini-card gradient-card">
          <span>AI 解析摘要</span>
          <p>{{ current.summary }}</p>
        </article>
      </div>
    </div>
  </PanelSection>
</template>

<style scoped>
.project-setup {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.95fr);
  gap: 18px;
}
.story-input-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.story-input-card textarea {
  min-height: 240px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  color: var(--text-muted);
  padding: 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.6;
}
.input-footer {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-faint);
}
.setup-side {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.mini-card {
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.mini-card span {
  display: block;
  font-size: 12px;
  color: var(--text-faint);
  text-transform: uppercase;
  margin-bottom: 12px;
}
.mini-card ul {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  color: var(--text-muted);
}
.gradient-card {
  background: linear-gradient(135deg, rgba(138, 140, 255, 0.05), rgba(255, 255, 255, 0.02));
}
.tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}
.tag.warm {
  color: var(--warning);
  background: rgba(241, 163, 75, 0.1);
}
.parse-banner {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--panel-border);
  margin-bottom: 18px;
  background: rgba(255, 255, 255, 0.03);
}
.parse-banner.running {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.parse-banner.error {
  background: rgba(240, 89, 89, 0.08);
  border-color: var(--danger);
}
.parse-banner-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  color: var(--text-primary);
  font-size: 13px;
}
.parse-banner p {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}
.empty-cta {
  padding: 32px;
  text-align: center;
  background: var(--accent-dim);
  border: 1px dashed var(--accent);
  border-radius: var(--radius-md);
  margin-bottom: 18px;
}
.empty-cta p {
  margin: 0 0 16px 0;
  color: var(--text-muted);
  font-size: 14px;
}
.primary-btn.large {
  font-size: 15px;
  padding: 12px 32px;
}
.ghost-btn.small {
  font-size: 12px;
  padding: 4px 10px;
}
</style>
```

- [ ] **Step 2: 手测**

1. 创建项目(走"保存草稿") → workbench 的 setup panel 显示空态大按钮
2. 点"开始拆分分镜" → 进度条出现,文案滚动(mock VolcanoClient eager 下几秒内终止)
3. 终态 `succeeded` → reload + toast "分镜已生成" + 空态按钮消失 + storyboard panel(Task 6)显示真实分镜
4. 若后端返回 500(手工 kill 后端)→ 红色 banner + 重试按钮;点重试再次触发

- [ ] **Step 3: typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: 无错。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/setup/ProjectSetupPanel.vue
git commit -m "feat(frontend): ProjectSetupPanel 触发 parse + useJobPolling 真实挂载 + 失败 banner"
```

---

## Task 5: 新增 `StoryboardEditorModal.vue` 组件(新增/编辑表单)

**Files:**
- Create: `frontend/src/components/storyboard/StoryboardEditorModal.vue`

**组件 props / emit**:
- props: `open: boolean`, `mode: "create" | "edit"`, `initial?: StoryboardShot`
- emits: `close()`, `submit(payload: StoryboardCreateRequest | StoryboardUpdateRequest)`

**表单字段**(与后端 schema 对齐):
- `title`:≤128 char
- `description`:多行
- `detail`:多行,允许空
- `duration_sec`:number,0–300,允许空
- `tags`:逗号分隔输入 → `string[]`

- [ ] **Step 1: 创建 `frontend/src/components/storyboard/StoryboardEditorModal.vue`**

```vue
<!-- frontend/src/components/storyboard/StoryboardEditorModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "@/components/common/Modal.vue";
import type { StoryboardShot } from "@/types";
import type { StoryboardCreateRequest, StoryboardUpdateRequest } from "@/types/api";

const props = defineProps<{
  open: boolean;
  mode: "create" | "edit";
  initial?: StoryboardShot | null;
}>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: StoryboardCreateRequest | StoryboardUpdateRequest): void;
}>();

const title = ref("");
const description = ref("");
const detail = ref("");
const durationSec = ref<number | null>(null);
const tagsInput = ref("");
const submitting = ref(false);

/** "3.5 秒" → 3.5;空串 → null */
function parseDurationFromDisplay(raw: string): number | null {
  const m = raw.match(/([0-9]+(?:\.[0-9]+)?)/);
  return m ? Number(m[1]) : null;
}

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    submitting.value = false;
    if (props.mode === "edit" && props.initial) {
      title.value = props.initial.title;
      description.value = props.initial.description;
      detail.value = props.initial.detail ?? "";
      durationSec.value = parseDurationFromDisplay(props.initial.duration);
      tagsInput.value = (props.initial.tags ?? []).join(", ");
    } else {
      title.value = "";
      description.value = "";
      detail.value = "";
      durationSec.value = null;
      tagsInput.value = "";
    }
  },
  { immediate: true }
);

const durationError = computed(() => {
  const v = durationSec.value;
  if (v === null) return "";
  if (Number.isNaN(v)) return "时长必须是数字";
  if (v < 0 || v > 300) return "时长范围 0–300 秒";
  return "";
});
const titleError = computed(() => {
  if (title.value.length > 128) return "标题最长 128 字";
  return "";
});

const canSubmit = computed(
  () => !durationError.value && !titleError.value && !submitting.value
);

function parsedTags(): string[] {
  return tagsInput.value
    .split(/[,，]/)
    .map((t) => t.trim())
    .filter(Boolean);
}

function tagsChanged(orig: string[] | null | undefined, next: string[]): boolean {
  return JSON.stringify(orig ?? []) !== JSON.stringify(next);
}

function onSubmit() {
  if (!canSubmit.value) return;
  submitting.value = true;
  const tags = parsedTags();
  if (props.mode === "create") {
    const payload: StoryboardCreateRequest = {
      title: title.value.trim(),
      description: description.value,
      detail: detail.value === "" ? null : detail.value,
      duration_sec: durationSec.value,
      tags: tags.length > 0 ? tags : null
    };
    emit("submit", payload);
  } else {
    // edit:只发送改动的字段(显式 undefined 即不发)
    const payload: StoryboardUpdateRequest = {};
    if (props.initial) {
      if (title.value !== props.initial.title) payload.title = title.value.trim();
      if (description.value !== props.initial.description) payload.description = description.value;
      const origDetail = props.initial.detail ?? "";
      if (detail.value !== origDetail) payload.detail = detail.value === "" ? null : detail.value;
      // duration_sec 后端 PATCH 禁止显式 null(_reject_explicit_null);
      // 仅在用户"明确填了一个新数字"时下发。清空时不发送,UI 已在 template 里给出提示。
      const origDuration = parseDurationFromDisplay(props.initial.duration);
      if (durationSec.value !== null && durationSec.value !== origDuration) {
        payload.duration_sec = durationSec.value;
      }
      if (tagsChanged(props.initial.tags, tags)) payload.tags = tags;
    }
    emit("submit", payload);
  }
}
</script>

<template>
  <Modal :open="open" :title="mode === 'create' ? '新增镜头' : '编辑镜头'" @close="emit('close')">
    <form class="storyboard-form" @submit.prevent="onSubmit">
      <label>
        <span>镜头标题</span>
        <input v-model="title" maxlength="128" placeholder="如:皇城夜雨,山雨欲来" />
        <em v-if="titleError" class="err">{{ titleError }}</em>
      </label>
      <label>
        <span>文案描述</span>
        <textarea v-model="description" rows="3" />
      </label>
      <label>
        <span>镜头细节(可空)</span>
        <textarea v-model="detail" rows="4" />
      </label>
      <div class="form-row">
        <label>
          <span>时长(秒, 0–300, 可空)</span>
          <input v-model.number="durationSec" type="number" min="0" max="300" step="0.1" />
          <em v-if="durationError" class="err">{{ durationError }}</em>
          <em v-if="mode === 'edit' && initial && initial.duration && durationSec === null" class="hint">
            时长不可清空,如需重置请先保存其他修改,下一版会放开清空支持
          </em>
        </label>
        <label>
          <span>标签(逗号分隔)</span>
          <input v-model="tagsInput" placeholder="古风, 夜景, 中景" />
        </label>
      </div>
    </form>
    <template #footer>
      <button class="ghost-btn" @click="emit('close')">取消</button>
      <button class="primary-btn" :disabled="!canSubmit" @click="onSubmit">
        {{ mode === "create" ? "新增" : "保存" }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.storyboard-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.storyboard-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}
.storyboard-form input,
.storyboard-form textarea {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font: inherit;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.err {
  color: var(--danger);
  font-size: 12px;
  font-style: normal;
}
.hint {
  color: var(--warning);
  font-size: 12px;
  font-style: normal;
}
</style>
```

- [ ] **Step 2: typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: 无错。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/storyboard/StoryboardEditorModal.vue
git commit -m "feat(frontend): 新增 StoryboardEditorModal(新建/编辑表单)"
```

---

## Task 6: `StoryboardPanel` 升级 — 卡片操作 + 新增 + 删除 + 上/下移 + 阶段门

**Files:**
- Modify: `frontend/src/components/storyboard/StoryboardPanel.vue`

**交互规则(前端 spec §7.3.2 + §8)**:

| stage_raw | 顶部"新增镜头" | 卡片上移/下移/编辑/删除 | 顶部"确认 N 镜头" |
| --- | --- | --- | --- |
| `draft` | 可用 | 可用 | Task 7 交付,当前占位 disabled |
| `storyboard_ready` | 可用 | 可用 | Task 7 交付 |
| 其他 | disabled + 悬浮提示 "当前阶段已锁定,如需修改请 **回退阶段**"(点按钮打开 rollback modal) | 同左 | disabled |

- [ ] **Step 1: 全量替换 `frontend/src/components/storyboard/StoryboardPanel.vue`**

```vue
<!-- frontend/src/components/storyboard/StoryboardPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import StoryboardEditorModal from "./StoryboardEditorModal.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useToast } from "@/composables/useToast";
import { confirm as uiConfirm } from "@/composables/useConfirm";
import { ApiError, messageFor } from "@/utils/error";
import type { StoryboardShot } from "@/types";
import type { StoryboardCreateRequest, StoryboardUpdateRequest } from "@/types/api";

const store = useWorkbenchStore();
const { current, currentShot, selectedShotId } = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const editorOpen = ref(false);
const editorMode = ref<"create" | "edit">("create");
const editorInitial = ref<StoryboardShot | null>(null);
const rollbackOpen = ref(false);
const busy = ref(false);

const lockedTip = "当前阶段已锁定,如需修改请 回退阶段";
// 已确认后想改分镜需回退到 draft 或 storyboard_ready(回退 modal 内收敛目标)
const alreadyConfirmedTip = "已确认。如需修改分镜请 回退阶段";

const confirmLabel = computed(() => {
  const n = current.value?.storyboards.length ?? 0;
  return `确认 ${n} 个镜头`;
});

function guardEdit(): boolean {
  if (flags.value.canEditStoryboards) return true;
  toast.warning(lockedTip, {
    action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
  });
  return false;
}

function openCreate() {
  if (!guardEdit()) return;
  editorMode.value = "create";
  editorInitial.value = null;
  editorOpen.value = true;
}

function openEdit(shot: StoryboardShot) {
  if (!guardEdit()) return;
  editorMode.value = "edit";
  editorInitial.value = shot;
  editorOpen.value = true;
}

async function handleSubmit(
  payload: StoryboardCreateRequest | StoryboardUpdateRequest
) {
  busy.value = true;
  try {
    if (editorMode.value === "create") {
      await store.createShot(payload as StoryboardCreateRequest);
      toast.success("镜头已新增");
    } else if (editorInitial.value) {
      await store.updateShot(editorInitial.value.id, payload as StoryboardUpdateRequest);
      toast.success("镜头已保存");
    }
    editorOpen.value = false;
  } catch (e) {
    if (e instanceof ApiError && e.code === 40301) {
      toast.warning(lockedTip, {
        action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
      });
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("操作失败");
    }
  } finally {
    busy.value = false;
  }
}

async function removeShot(shot: StoryboardShot) {
  if (!guardEdit()) return;
  const ok = await uiConfirm({
    title: "删除镜头",
    body: `确定删除镜头 ${String(shot.index).padStart(2, "0")} 「${shot.title}」?该操作不可撤销。`,
    confirmText: "删除",
    danger: true
  });
  if (!ok) return;
  busy.value = true;
  try {
    await store.deleteShot(shot.id);
    toast.success("镜头已删除");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "删除失败");
  } finally {
    busy.value = false;
  }
}

async function moveUp(shot: StoryboardShot) {
  if (!guardEdit()) return;
  busy.value = true;
  try {
    await store.moveShotUp(shot.id);
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "重排失败");
  } finally {
    busy.value = false;
  }
}
async function moveDown(shot: StoryboardShot) {
  if (!guardEdit()) return;
  busy.value = true;
  try {
    await store.moveShotDown(shot.id);
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "重排失败");
  } finally {
    busy.value = false;
  }
}

const shots = computed(() => current.value?.storyboards ?? []);
const isFirst = (shot: StoryboardShot) => shots.value[0]?.id === shot.id;
const isLast = (shot: StoryboardShot) => shots.value[shots.value.length - 1]?.id === shot.id;

// 空态文案按 stage 区分:draft 指向 setup panel 的大按钮;其他 stage 说明需回退或新增
const emptyHint = computed(() => {
  if (current.value?.stage_raw === "draft") {
    return "尚未生成分镜 · 请先在上方 Setup Panel 点 '开始拆分分镜'";
  }
  return "当前项目还没有镜头 · 点顶部 '+ 新增镜头' 开始手动编排,或回退到 draft 重新解析";
});
</script>

<template>
  <PanelSection v-if="current" kicker="02" title="分镜工作台">
    <template #actions>
      <button
        class="ghost-btn"
        type="button"
        :disabled="busy"
        :title="flags.canEditStoryboards ? '' : lockedTip"
        @click="openCreate"
      >
        + 新增镜头
      </button>
      <!-- Task 7 在下一步把这个按钮接入 /confirm;Task 6 先以 disabled 占位 -->
      <button class="primary-btn" type="button" disabled>
        {{ confirmLabel }}
      </button>
    </template>

    <div v-if="!shots.length" class="empty-note">
      {{ emptyHint }}
    </div>
    <div v-else class="storyboard-layout">
      <div class="storyboard-grid">
        <article
          v-for="shot in shots"
          :key="shot.id"
          class="story-card"
          :class="{ active: selectedShotId === shot.id }"
          @click="store.selectShot(shot.id)"
        >
          <div class="card-head">
            <span>{{ String(shot.index).padStart(2, "0") }}</span>
            <div class="card-actions" @click.stop>
              <button
                class="icon-btn"
                :disabled="!flags.canEditStoryboards || busy || isFirst(shot)"
                :title="flags.canEditStoryboards ? '上移' : lockedTip"
                @click="moveUp(shot)"
              >↑</button>
              <button
                class="icon-btn"
                :disabled="!flags.canEditStoryboards || busy || isLast(shot)"
                :title="flags.canEditStoryboards ? '下移' : lockedTip"
                @click="moveDown(shot)"
              >↓</button>
              <button
                class="icon-btn"
                :disabled="busy"
                :title="flags.canEditStoryboards ? '编辑' : lockedTip"
                @click="openEdit(shot)"
              >✎</button>
              <button
                class="icon-btn danger"
                :disabled="busy"
                :title="flags.canEditStoryboards ? '删除' : lockedTip"
                @click="removeShot(shot)"
              >✕</button>
            </div>
          </div>
          <strong>{{ shot.title }}</strong>
          <p>{{ shot.description }}</p>
        </article>
      </div>

      <div v-if="currentShot" class="storyboard-detail">
        <div class="detail-title">
          <h3>
            当前镜头：{{ String(currentShot.index).padStart(2, "0") }}
            {{ currentShot.title }}
          </h3>
          <span v-if="currentShot.duration">时长建议 {{ currentShot.duration }}</span>
        </div>
        <p>{{ currentShot.detail }}</p>
        <div class="detail-tags">
          <span v-for="tag in currentShot.tags" :key="tag">{{ tag }}</span>
        </div>
      </div>
    </div>

    <StoryboardEditorModal
      :open="editorOpen"
      :mode="editorMode"
      :initial="editorInitial"
      @close="editorOpen = false"
      @submit="handleSubmit"
    />
    <StageRollbackModal :open="rollbackOpen" @close="rollbackOpen = false" />
  </PanelSection>
</template>

<style scoped>
.storyboard-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.9fr);
  gap: 18px;
}
.storyboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.story-card {
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 160ms;
}
.story-card.active {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.card-head span {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(138, 140, 255, 0.1);
  color: var(--accent);
  font-size: 12px;
}
.card-actions {
  display: flex;
  gap: 4px;
}
.icon-btn {
  width: 26px;
  height: 26px;
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
}
.icon-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.icon-btn.danger:hover:not(:disabled) {
  color: var(--danger);
  border-color: var(--danger);
}
.story-card strong {
  display: block;
  font-size: 15px;
  margin-bottom: 8px;
}
.story-card p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}
.storyboard-detail {
  padding: 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.detail-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.detail-title h3 {
  margin: 0;
  font-size: 18px;
}
.detail-title span {
  font-size: 12px;
  color: var(--text-faint);
}
.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.detail-tags span {
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-muted);
}
.empty-note {
  padding: 40px 0;
  text-align: center;
  color: var(--text-faint);
  font-size: 14px;
}
</style>
```

- [ ] **Step 2: 手测**

- `stage=草稿中`(parse 完成后 stage=storyboard_ready,这里假设 parse 已跑完):顶部 "+ 新增镜头" 可点
- 点击新增镜头 → 弹 modal → 填写 title/描述 → 保存 → reload 后新镜头出现在最后
- 编辑镜头 → 改 title → 保存 → 卡片文案更新
- 上移/下移:第一张上移禁用,最后一张下移禁用,其他可用,点击后顺序变化
- 删除:二次确认 modal → 删除后重排(`delete` 后端会自动压缩 idx)
- 手工把 `stage_raw` 强制设为 `characters_locked`(SQL:`UPDATE projects SET stage = 'characters_locked' WHERE id=…`)→ 所有写按钮禁用 + 悬浮显示锁定提示;点禁用按钮或触发到 403 时弹"回退阶段"快捷入口
- 单测会在 Task 9 覆盖 store 动作

- [ ] **Step 3: typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: 无错。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/storyboard/StoryboardPanel.vue
git commit -m "feat(frontend): StoryboardPanel 可交互 — 新增/编辑/删除/上下移 + 阶段门"
```

---

## Task 7: StoryboardPanel 升级 — "确认 N 个镜头" 接入 `/confirm`

**Files:**
- Modify: `frontend/src/components/storyboard/StoryboardPanel.vue`

> **依赖 Task 6**:本 Task 在 Task 6 已交付的 `StoryboardPanel.vue` 之上**追加**内容(`<script setup>` 里新增 state / action,模板里替换 `confirmLabel` 按钮一处)。不是全量替换;`lockedTip` / `alreadyConfirmedTip` / `confirmLabel` / `guardEdit` / `shots` 等标识符均由 Task 6 定义。

**交互规则**:
- 顶部 "确认 N 个镜头" 按钮:
  - `stage_raw === "draft"` 且 `storyboards.length > 0` → 可点;点击触发 `/confirm`,`stage_raw` 推进到 `storyboard_ready`;toast "分镜已确认,进入角色阶段"
  - `stage_raw === "storyboard_ready"` → 已经确认过,按钮显示 "已确认"(disabled,ghost 样式)
  - 其他阶段 → disabled + 锁定提示
  - 没有分镜时(0 个) → 按钮 disabled,文案 "确认 0 个镜头",悬浮提示 "请先新增镜头"

- [ ] **Step 1: 修改 `StoryboardPanel.vue` 中"确认镜头"按钮部分**

在 `<script setup>` 里,增加 `confirming` 状态和 `onConfirm` 动作:

```ts
const confirming = ref(false);
const alreadyConfirmed = computed(() => current.value?.stage_raw !== "draft");
const canConfirm = computed(
  () =>
    current.value?.stage_raw === "draft" &&
    shots.value.length > 0 &&
    !confirming.value
);
const confirmTooltip = computed(() => {
  if (alreadyConfirmed.value) return alreadyConfirmedTip;
  if (shots.value.length === 0) return "请先新增镜头";
  return "";
});

async function onConfirm() {
  if (!canConfirm.value) return;
  const ok = await uiConfirm({
    title: "确认分镜",
    body: `将确认 ${shots.value.length} 个镜头并进入下一阶段。确认后若需修改需先回退到 draft。`,
    confirmText: "确认",
    danger: false
  });
  if (!ok) return;
  confirming.value = true;
  try {
    await store.confirmStoryboards();
    toast.success("分镜已确认,进入角色阶段");
  } catch (e) {
    if (e instanceof ApiError && e.code === 40901) {
      toast.warning(messageFor(e.code, e.message));
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("确认失败");
    }
  } finally {
    confirming.value = false;
  }
}
```

并替换模板里 `<button class="primary-btn" type="button" disabled ...>` 那行为:

```html
<button
  class="primary-btn"
  type="button"
  :disabled="!canConfirm || alreadyConfirmed"
  :title="confirmTooltip"
  @click="onConfirm"
>
  {{ alreadyConfirmed ? "已确认" : confirming ? "确认中..." : confirmLabel }}
</button>
```

- [ ] **Step 2: 手测**

- 新建项目 → parse 成功 → `stage_raw=storyboard_ready` → 顶部按钮显示 "已确认",disabled
- 如果想测 draft → storyboard_ready 路径:手工 SQL `UPDATE projects SET stage='draft' WHERE id=…`;reload 前端;`+ 新增镜头` 一个;点 "确认 N 个镜头" → 二次确认 modal → 确认 → toast + reload + 按钮变 "已确认"
- 0 镜头时按钮 disabled,悬浮显示"请先新增镜头"

- [ ] **Step 3: typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: 无错。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/storyboard/StoryboardPanel.vue
git commit -m "feat(frontend): StoryboardPanel 顶部 '确认 N 镜头' 接入 /storyboards/confirm"
```

---

## Task 8: `WorkbenchView` — 进入时若带 parse job 自动衔接轮询

**Files:**
- Modify: `frontend/src/views/WorkbenchView.vue`

**动机**:从 `ProjectCreateView` 点"开始拆分分镜"跳到 workbench 时,`workbench.activeParseJobId` 已经被设置,但路由切换会重建组件,需要确保 `load(id)` 之后 `ProjectSetupPanel` 里的 `useJobPolling(activeParseJobId)` 能自动开始轮询(已由 Task 4 覆盖,watch `immediate: true`)。

本任务的额外工作是:**当用户手动刷新 workbench 页面时,不残留上次的 `activeParseJobId`**,否则会对着已完成的 job 无意义 polling。处理方法:`WorkbenchView.onMounted` 里若当前 project 的 `stage_raw !== "draft"`,清掉 `activeParseJobId`。

- [ ] **Step 1: 修改 `WorkbenchView.vue` 的 `loadCurrent`**

在 `loadCurrent` 里,`store.load(...)` 成功后追加:

```ts
// 若项目已过 draft 阶段,上一个 parse job 必然已结束,清掉 job id 避免空转轮询
if (store.current?.stage_raw && store.current.stage_raw !== "draft") {
  store.markParseSucceeded();
}
```

完整方法:

```ts
async function loadCurrent() {
  try {
    await store.load(String(route.params.id));
    if (store.current?.stage_raw && store.current.stage_raw !== "draft") {
      store.markParseSucceeded();
    }
  } catch (e) {
    if (e instanceof ApiError && e.code === 40401) {
      toast.error("项目不存在");
      await router.replace({ name: "project-list" });
    } else {
      toast.error(e instanceof Error ? e.message : "加载失败");
    }
  }
}
```

- [ ] **Step 2: 手测**

- 刷新一个 `stage_raw=storyboard_ready` 的 workbench 页 → 查看 DevTools Network,不应持续有 `/jobs/{id}` 请求
- 如果从 create 页跳过来(带 `activeParseJobId`)→ setup panel 立即开始轮询

- [ ] **Step 3: typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: 无错。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/WorkbenchView.vue
git commit -m "fix(frontend): 刷新 workbench 时清残留 activeParseJobId 避免空转轮询"
```

---

## Task 9: 单测 — `api/storyboards` + workbench store shot 动作

**Files:**
- Create: `frontend/tests/unit/storyboards.api.spec.ts`
- Create: `frontend/tests/unit/workbench.store.spec.ts`

- [ ] **Step 1: 创建 `frontend/tests/unit/storyboards.api.spec.ts`**

```ts
/* frontend/tests/unit/storyboards.api.spec.ts */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { client } from "@/api/client";
import { storyboardsApi } from "@/api/storyboards";

vi.mock("@/api/client", () => ({
  client: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn()
  }
}));

const mocked = client as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("storyboardsApi", () => {
  it("list GETs /projects/:id/storyboards", async () => {
    mocked.get.mockResolvedValue({ data: [] });
    const out = await storyboardsApi.list("P1");
    expect(mocked.get).toHaveBeenCalledWith("/projects/P1/storyboards");
    expect(out).toEqual([]);
  });

  it("create POSTs payload as-is", async () => {
    mocked.post.mockResolvedValue({ data: { id: "S1" } });
    await storyboardsApi.create("P1", { title: "t", description: "d", idx: 2 });
    expect(mocked.post).toHaveBeenCalledWith("/projects/P1/storyboards", {
      title: "t",
      description: "d",
      idx: 2
    });
  });

  it("update PATCHes shot path with body", async () => {
    mocked.patch.mockResolvedValue({ data: { id: "S1" } });
    await storyboardsApi.update("P1", "S1", { title: "new" });
    expect(mocked.patch).toHaveBeenCalledWith("/projects/P1/storyboards/S1", {
      title: "new"
    });
  });

  it("remove DELETEs and returns deleted flag", async () => {
    mocked.delete.mockResolvedValue({ data: { deleted: true } });
    const out = await storyboardsApi.remove("P1", "S1");
    expect(mocked.delete).toHaveBeenCalledWith("/projects/P1/storyboards/S1");
    expect(out).toEqual({ deleted: true });
  });

  it("reorder POSTs ordered_ids", async () => {
    mocked.post.mockResolvedValue({ data: { reordered: 3 } });
    await storyboardsApi.reorder("P1", { ordered_ids: ["a", "b", "c"] });
    expect(mocked.post).toHaveBeenCalledWith("/projects/P1/storyboards/reorder", {
      ordered_ids: ["a", "b", "c"]
    });
  });

  it("confirm POSTs with empty body", async () => {
    mocked.post.mockResolvedValue({
      data: { stage: "storyboard_ready", stage_raw: "storyboard_ready" }
    });
    const out = await storyboardsApi.confirm("P1");
    expect(mocked.post).toHaveBeenCalledWith("/projects/P1/storyboards/confirm");
    expect(out.stage_raw).toBe("storyboard_ready");
  });
});
```

- [ ] **Step 2: 创建 `frontend/tests/unit/workbench.store.spec.ts`**

```ts
/* frontend/tests/unit/workbench.store.spec.ts */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/projects", () => ({
  projectsApi: {
    parse: vi.fn(),
    get: vi.fn(),
    rollback: vi.fn()
  }
}));
vi.mock("@/api/storyboards", () => ({
  storyboardsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    reorder: vi.fn(),
    confirm: vi.fn()
  }
}));

import { projectsApi } from "@/api/projects";
import { storyboardsApi } from "@/api/storyboards";
import { useWorkbenchStore } from "@/store/workbench";

const FAKE_PROJECT = {
  id: "P1",
  name: "proj",
  stage: "草稿中",
  stage_raw: "draft",
  genre: null,
  ratio: "",
  suggestedShots: "",
  story: "",
  summary: "",
  parsedStats: [],
  setupParams: [],
  projectOverview: "",
  storyboards: [
    { id: "A", index: 1, title: "a", description: "", detail: "", duration: "", tags: [] },
    { id: "B", index: 2, title: "b", description: "", detail: "", duration: "", tags: [] },
    { id: "C", index: 3, title: "c", description: "", detail: "", duration: "", tags: [] }
  ],
  characters: [],
  scenes: [],
  generationProgress: "",
  generationNotes: { input: "", suggestion: "" },
  generationQueue: [],
  exportConfig: [],
  exportDuration: "",
  exportTasks: []
};

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  (projectsApi.get as ReturnType<typeof vi.fn>).mockResolvedValue(FAKE_PROJECT);
});

describe("workbench store", () => {
  it("startParse stores job_id in activeParseJobId", async () => {
    (projectsApi.parse as ReturnType<typeof vi.fn>).mockResolvedValue({ job_id: "J1" });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jid = await store.startParse();
    expect(projectsApi.parse).toHaveBeenCalledWith("P1");
    expect(jid).toBe("J1");
    expect(store.activeParseJobId).toBe("J1");
  });

  it("markParseSucceeded clears activeParseJobId", async () => {
    const store = useWorkbenchStore();
    await store.load("P1");
    (projectsApi.parse as ReturnType<typeof vi.fn>).mockResolvedValue({ job_id: "J1" });
    await store.startParse();
    store.markParseSucceeded();
    expect(store.activeParseJobId).toBeNull();
    expect(store.parseError).toBeNull();
  });

  it("markParseFailed sets parseError", async () => {
    const store = useWorkbenchStore();
    await store.load("P1");
    store.markParseFailed("upstream 503");
    expect(store.parseError).toBe("upstream 503");
    expect(store.activeParseJobId).toBeNull();
  });

  it("moveShotUp sends reorder with swapped ids", async () => {
    const store = useWorkbenchStore();
    await store.load("P1");
    (storyboardsApi.reorder as ReturnType<typeof vi.fn>).mockResolvedValue({ reordered: 3 });
    await store.moveShotUp("B");
    expect(storyboardsApi.reorder).toHaveBeenCalledWith("P1", {
      ordered_ids: ["B", "A", "C"]
    });
  });

  it("moveShotUp on first shot is a no-op", async () => {
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.moveShotUp("A");
    expect(storyboardsApi.reorder).not.toHaveBeenCalled();
  });

  it("moveShotDown on last shot is a no-op", async () => {
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.moveShotDown("C");
    expect(storyboardsApi.reorder).not.toHaveBeenCalled();
  });

  it("deleteShot clears selectedShotId if equal", async () => {
    const store = useWorkbenchStore();
    await store.load("P1");
    store.selectShot("B");
    (storyboardsApi.remove as ReturnType<typeof vi.fn>).mockResolvedValue({ deleted: true });
    await store.deleteShot("B");
    // reload 后 selectedShotId 被 load() 里的保护逻辑重置到首个
    expect(store.selectedShotId).toBe("A");
  });

  it("confirmStoryboards POSTs and reloads", async () => {
    const store = useWorkbenchStore();
    await store.load("P1");
    (storyboardsApi.confirm as ReturnType<typeof vi.fn>).mockResolvedValue({
      stage: "storyboard_ready",
      stage_raw: "storyboard_ready"
    });
    const resp = await store.confirmStoryboards();
    expect(storyboardsApi.confirm).toHaveBeenCalledWith("P1");
    expect(resp.stage_raw).toBe("storyboard_ready");
    // reload 在 load() 里被调用一次(初始)+ confirmStoryboards 后一次 = 2
    expect(projectsApi.get).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 3: 跑通**

Run: `cd frontend && pnpm test`
Expected: 原有 3 个测试文件 + 新增 2 个文件全部通过;新增用例总数 6 + 8 = 14(大致)。

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/unit/storyboards.api.spec.ts frontend/tests/unit/workbench.store.spec.ts
git commit -m "test(frontend): storyboards API + workbench store M2 动作单测"
```

---

## Task 10: 冒烟脚本 `scripts/smoke_m2.sh` + README 更新

**Files:**
- Create: `frontend/scripts/smoke_m2.sh`
- Modify: `frontend/README.md`

- [ ] **Step 1: 创建 `frontend/scripts/smoke_m2.sh`**

```bash
#!/usr/bin/env bash
# frontend/scripts/smoke_m2.sh —— M2 前端 ↔ 后端 parse + storyboards 冒烟
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BE=${BE:-http://127.0.0.1:8000}
FE=${FE:-http://127.0.0.1:5173}

export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"
FE_PID_FILE=${FE_PID_FILE:-/tmp/comic-drama-fe.pid}
FE_LOG_FILE=${FE_LOG_FILE:-/tmp/comic-drama-fe.log}

cleanup() {
  if [[ -f "$FE_PID_FILE" ]]; then
    FE_PID="$(cat "$FE_PID_FILE")"
    kill "$FE_PID" 2>/dev/null || true
    wait "$FE_PID" 2>/dev/null || true
    rm -f "$FE_PID_FILE"
  fi
}
trap cleanup EXIT

echo "[1/8] 后端健康检查"
curl -fsS --noproxy "*" "$BE/healthz" | jq '.data'

echo "[2/8] 前端 typecheck + build"
( cd "$REPO_ROOT/frontend" && npm run typecheck && npm run build )

echo "[3/8] 启动前端 dev server"
( cd "$REPO_ROOT/frontend" && exec npm run dev >"$FE_LOG_FILE" 2>&1 ) &
echo $! > "$FE_PID_FILE"

echo "Waiting for frontend on $FE..."
for i in {1..20}; do
  if curl -s --noproxy "*" "$FE" > /dev/null; then
    echo "Frontend is up!"
    break
  fi
  if [[ $i -eq 20 ]]; then
    echo "Frontend failed to start. Logs:"
    cat "$FE_LOG_FILE"
    exit 1
  fi
  sleep 1
done

STORY=$(python3 -c 'print("从前有座山,山上有座庙..." * 10)')

echo "[4/8] 创建项目"
PID=$(curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg name '前端 M2 冒烟' --arg story "$STORY" '{name:$name, story:$story}')" \
  | jq -r .data.id)
echo "created: $PID"

echo "[5/8] 触发 parse"
JOB_ID=$(curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects/$PID/parse" | jq -r .data.job_id)
echo "parse job: $JOB_ID"

echo "[6/8] 轮询 job(EAGER 模式应已终态)"
for i in {1..20}; do
  STATUS=$(curl -fsS --noproxy "*" "$FE/api/v1/jobs/$JOB_ID" | jq -r .data.status)
  echo "  job status: $STATUS"
  if [[ "$STATUS" == "succeeded" ]]; then break; fi
  if [[ "$STATUS" == "failed" || "$STATUS" == "canceled" ]]; then
    curl -s --noproxy "*" "$FE/api/v1/jobs/$JOB_ID" | jq .
    exit 1
  fi
  sleep 1
done
[[ "$STATUS" == "succeeded" ]] || { echo "job did not reach succeeded in 20s"; exit 1; }

echo "[7/8] 校验分镜列表 + stage_raw"
N=$(curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID/storyboards" | jq '.data | length')
echo "  storyboards count: $N"
[[ "$N" -ge 1 ]] || { echo "expected >=1 storyboard"; exit 1; }

STAGE=$(curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID" | jq -r .data.stage_raw)
echo "  stage_raw: $STAGE"
[[ "$STAGE" == "storyboard_ready" ]] || { echo "expected storyboard_ready, got $STAGE"; exit 1; }

# 再做一轮 reorder 往返:反转
IDS=$(curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID/storyboards" | jq -c '[.data[].id] | reverse')
curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects/$PID/storyboards/reorder" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --argjson ids "$IDS" '{ordered_ids: $ids}')" | jq '.data'

echo "[8/8] 清理"
curl -fsS --noproxy "*" -X DELETE "$FE/api/v1/projects/$PID" | jq .

echo "✅ frontend M2 smoke passed"
```

- [ ] **Step 2: 标记可执行**

```bash
chmod +x frontend/scripts/smoke_m2.sh
```

- [ ] **Step 3: 更新 `frontend/README.md` — 追加"M2 范围"一节**

在 M1 范围段落之后插入:

```markdown
## M2 范围

M2 在 M1 的项目 CRUD 之上打通了 AI 解析 + 分镜编辑链路。

### 新增端点对接

| 端点 | 组件 / Store |
| --- | --- |
| `POST /api/v1/projects/{id}/parse` | `ProjectCreateView`(开始拆分分镜按钮)/ `ProjectSetupPanel`(空态大按钮) |
| `GET /api/v1/jobs/{id}` | `useJobPolling` → `ProjectSetupPanel` 真实轮询 |
| `GET /api/v1/projects/{id}/storyboards` | 读路径仍由 `GET /projects/{id}` 聚合,M2 未单独使用 |
| `POST /api/v1/projects/{id}/storyboards` | `StoryboardPanel` 新增镜头 |
| `PATCH /api/v1/projects/{id}/storyboards/{shot_id}` | `StoryboardPanel` 编辑镜头 |
| `DELETE /api/v1/projects/{id}/storyboards/{shot_id}` | `StoryboardPanel` 删除镜头 |
| `POST /api/v1/projects/{id}/storyboards/reorder` | `StoryboardPanel` 上移/下移 |
| `POST /api/v1/projects/{id}/storyboards/confirm` | `StoryboardPanel` 顶部"确认 N 镜头" |

### 本地联调

```bash
# 1) 启动后端(务必 EAGER 模式,mock VolcanoClient 当场跑完)
cd backend && CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload

# 2) 启动前端
cd frontend && pnpm dev

# 3) 冒烟
./frontend/scripts/smoke_m2.sh
```

### 阶段门(useStageGate)在 M2 的生效点

- 分镜编辑窗口:`stage_raw ∈ {draft, storyboard_ready}`;其他 stage 下所有写按钮灰化并悬浮提示 "当前阶段已锁定,如需修改请 回退阶段"
- 点击被锁定的写按钮或后端返回 40301 时,顶栏 toast 附带 "回退阶段" 快捷入口,打开 `StageRollbackModal`

### M2 不包含

- 角色 / 场景资产生成、镜头渲染、导出(M3a+)
- 分镜拖拽排序(使用 ↑ ↓ 按钮;拖拽进 M3a+)
- 分镜 `duration_sec` 批量调整(M3c+)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/scripts/smoke_m2.sh frontend/README.md
git commit -m "docs(frontend): M2 冒烟脚本 + README(parse + storyboards 链路)"
```

---

## Task 11: DoD 全量跑一遍

**Files:** 无(只跑命令)

- [ ] **Step 1: typecheck + build + test**

```bash
cd frontend
pnpm install              # 幂等,保证 lockfile 对齐
pnpm typecheck
pnpm build
pnpm test
```

Expected:
- typecheck: 0 error
- build: `vue-tsc --noEmit && vite build` 全绿
- test: 5 个 spec 文件全部通过(`error.spec.ts` / `useJobPolling.spec.ts` / `useStageGate.spec.ts` / `storyboards.api.spec.ts` / `workbench.store.spec.ts`)

- [ ] **Step 2: 后端冒烟**

```bash
cd backend && CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload &
# 等待后端起来
sleep 3
cd .. && ./frontend/scripts/smoke_m2.sh
```

Expected: `✅ frontend M2 smoke passed`

- [ ] **Step 3: 手测检查点**

1. `/projects/new` 走"开始拆分分镜" → 跳 workbench → setup panel 自动进入轮询 → 终态 reload → 分镜可见
2. `/projects/new` 走"保存草稿" → 跳 workbench → setup panel 显示空态大按钮 → 点大按钮 → 同上
3. 分镜新增 / 编辑 / 删除 / 上下移 / 确认 全部可用(stage=draft)
4. 手工 SQL 把 stage 改成 `characters_locked` → reload → 所有写按钮灰化,点击触发回退入口
5. 点"回退阶段"→ 选 `draft` → 执行 → toast + reload + 写按钮恢复可用,分镜被清空(后端级联逻辑)

- [ ] **Step 4: 最后一次 commit(仅在之前漏 commit 时需要)**

```bash
git status
# 若干净则跳过;否则补 commit
```

---

## 完成标准 (Definition of Done)

- [ ] `cd frontend && pnpm typecheck && pnpm build && pnpm test` 全绿
- [ ] `./frontend/scripts/smoke_m2.sh` 一次性通过(需后端 EAGER 模式先启动)
- [ ] 浏览器手测五点全部验证通过(见 Task 11 Step 3)
- [ ] `grep -RIn "M1 仅支持项目创建\|分镜解析等待 M2" frontend/src` 结果为空(M1 的占位文案已全部替换)
- [ ] `grep -RIn "disabled.*确认 N\|智能重排节奏" frontend/src` 结果为空(M1 的占位按钮已移除或接入)
- [ ] `useJobPolling` 确实在 `ProjectSetupPanel` 中被挂载(`grep -RIn "useJobPolling" frontend/src/components` 至少有 1 条命中)
- [ ] 阶段门 `useStageGate` 被 `StoryboardPanel` 使用(`grep -n "useStageGate" frontend/src/components/storyboard/StoryboardPanel.vue` 至少一条)
- [ ] git 提交历史按 Task 拆分:至少 10 个 M2 相关 commit(Task 1–10 各一次,Task 11 可不 commit)
- [ ] 不引入新运行时依赖(`package.json.dependencies` 与 M1 一致;本 plan 全程未新增)

---

## 自检(本 plan 写完后的 review)

- **Spec 覆盖**:前端 spec §15 M2 声明 "接入 mock 后端的 /parse + /storyboards/*;ProjectSetupPanel 和 StoryboardPanel 真实可交互;状态门初版 useStageGate 上线"。本 plan Task 1(api)/ Task 2(store)/ Task 3(create view)/ Task 4(setup panel + useJobPolling 挂载)/ Task 5–7(storyboard 编辑 + 确认)/ Task 8(workbench view)/ Task 9(测试)/ Task 10(冒烟 + README)覆盖齐全。spec §6.3 轮询语义(jobId null 停、终态停、onSuccess/onError handler)已由 M1 实现,M2 在 Task 4 真实挂载并接 reload;spec §7.3.2 的新增 / 编辑 / 上移 / 下移 / 删除 / 确认 N 镜头 / 锁定阶段灰化 / 回退入口 / 详情区对齐 全部在 Task 6–7 落地;spec §7.3.7 `StageRollbackModal` 无需再改,M2 在 panel 内新 mount 该组件作为 gate 拦截出口
- **Placeholder 扫描**:全文搜索 `TBD` / `TODO` / `implement later` / `fill in` / `占位` / `Similar to Task` 无命中(本文件仅有 "M1 的占位按钮已移除" 这种描述性文字)
- **与后端 M2 契约**:
  - `StoryboardDetail.duration_sec` / `idx` / `tags` 字段名与 backend M2 plan Task 10 Step 1 schema 完全一致
  - `StoryboardCreateRequest` 允许 `idx?: number | null`(null 追加到末)与后端 `StoryboardCreate.idx: int | None` 一致
  - `StoryboardUpdateRequest` 不含 `idx`(后端在 PATCH 上不暴露 idx,改 idx 通过 reorder)与后端 `StoryboardUpdate` schema 一致
  - `StoryboardUpdateRequest.detail?: string | null` 显式 null 允许(清空)与后端 `_reject_explicit_null` 规则的 detail 例外一致
  - `StoryboardUpdateRequest.duration_sec?: number`(非 null)与后端 `_reject_explicit_null` 禁止 duration_sec=null 一致;Task 5 的 `StoryboardEditorModal` 在 edit 模式下用 UI hint 告知用户"时长不可清空",避免隐式丢弃
  - `POST /parse` 成功响应 `{job_id}` 与后端 Task 11 Step 1 `return ok({"job_id": job.id})` 一致;Task 1 给 parse 单独放宽 axios timeout 到 60 s,EAGER + 真实 LLM 时也能扛住(M2 mock 下绰绰有余)
  - `POST /storyboards/confirm` 响应 `{stage, stage_raw}` 后端 Task 10 Step 3 原文 `return ok({"stage": project.stage, "stage_raw": project.stage})`,两者**都是 raw ENUM 字符串**(非中文展示串),与 `ProjectDetail.stage` 为中文的约定不一致。前端类型把两者都标为 `ProjectStageRaw` 以迎合当前实现;**已在后端 review 列表追踪**,若后端改为 `stage_zh(raw)` 前端需同步修 `StoryboardConfirmResponse.stage` 类型
- **Parse job 作用域**:`parseJob: { projectId, jobId } | null` 按项目作用域;`activeParseJobId` 是 `computed(() => pj.projectId === current.id ? pj.jobId : null)`。这能防住"A 项目 parse 中切到 B 项目 → B 的 SetupPanel 对着 A 的 jobId 轮询"的跨项目串台。`useJobPolling` 的 watch 在 `activeParseJobId` 变 null 时自动 cancel。
- **空态 CTA 不消失**:`ProjectSetupPanel.canStartParse` 故意不包含 `!startingParse.value`,`POST /parse` 进行中依然显示 CTA(按钮本身 disabled + 文案切"启动中..."),避免网络请求窗口期整块 UI 消失
- **阶段门一致性**:`StoryboardPanel` 的 `flags.canEditStoryboards` 与后端 `assert_storyboard_editable`(允许 `draft` / `storyboard_ready`)一致;confirm 按钮 `canConfirm = stage_raw === "draft" && shots.length > 0` 与后端 `StoryboardService.confirm`(仅在 draft 下前进到 storyboard_ready)一致;已在 storyboard_ready 及之后时前端显示 "已确认" + tooltip `alreadyConfirmedTip`(不再误导到 "回退到 draft",而是指向"回退阶段"让 rollback modal 自己选目标)
- **类型一致性**:`StoryboardShot`(展示,来自 `ProjectDetail.storyboards`,含 `index` / `duration` string)与 `StoryboardDetail`(raw,来自 `storyboardsApi`,含 `idx` / `duration_sec` number)刻意分离;所有写路径经 store 后 reload,避免两者混用
- **视觉不漂移**:Task 4 / Task 6 仅在原有类名基础上增加 `.card-head` / `.card-actions` / `.icon-btn` / `.parse-banner` / `.empty-cta` / `.hint` 等局部样式,未改动 demo 沿用的 `.story-card` / `.storyboard-grid` / `.storyboard-detail` / `.panel-section` 等骨架;配色沿用 `--accent` / `--danger` / `--warning` 变量

### 已知限制(M3a 再处理)

- 后端允许 `duration_sec=null` 的情况下,前端应放开 edit 模式的清空语义(当前 UI 给出 hint)
- `StoryboardConfirmResponse.stage` 语义与 `ProjectDetail.stage` 不一致(见上)
- `StageRollbackModal` 在 `WorkbenchView` 顶栏和 `StoryboardPanel` 内部各 mount 一份;理论上可同时打开,UI 上只是两层 scrim 叠加,交互无歧义。M3a 可收敛到 `provide/inject` 单例
- 分镜拖拽排序用 ↑ ↓ 按钮替代;拖拽等 M3a+

---

## 衔接下一份 plan

- **Frontend M3a**:对接后端 M3a 的 `/characters/generate` / `/scenes/generate` / `/regenerate` / `/lock` 端点。`CharacterAssetsPanel` / `SceneAssetsPanel` 从 M1 的只读空态升级为可交互:触发生成 job(`useJobPolling` 多并发) / 重生成参考图 / 锁定 / 编辑描述;场景的 `usage`(关联镜头)展开与批量绑定落地;版本历史入口的 UI 预留(真实后端 M3b 交付后再通)
- **关联依赖**:M3a 前端开始前,后端 M3a plan(`2026-04-21-backend-m3a-real-volcano-and-assets.md`)需交付:
  - `POST /api/v1/projects/{id}/characters/generate`(生成首批角色资产 + 参考图 job)
  - `POST /api/v1/projects/{id}/scenes/generate`(同上,场景)
  - `POST /api/v1/projects/{id}/characters/{char_id}/regenerate` / `POST /api/v1/projects/{id}/characters/{char_id}/lock`
  - 场景对应两端点
  - `ProjectDetail.characters` / `.scenes` 字段真实填充(M2 下 backend AggregateService 仍返回空数组)
- **阶段门延伸**:M3a 会用到 `canGenerateCharacters = storyboard_ready` / `canGenerateScenes = characters_locked` 两个已在 `useStageGate` 预埋的 flag;本 plan 不动 `useStageGate`
