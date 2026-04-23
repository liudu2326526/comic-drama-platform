# Frontend Minor: Shot Final Video Generation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留“生成草稿”能力，但把镜头区从“确认生成静帧”改造成“用户编辑草稿后直接生成最终成品视频”，并在面板内加入视频时长、分辨率、模型类型三组选择按钮，以及视频历史版本、播放预览、失败态与锁定最终版。

**Architecture:** 前端继续把 `render-draft` 当成一次性推荐输入，不落库；用户在 `GenerationPanel` 内编辑提示词、删改参考图并选择视频参数后，直接调用新的 `POST /video` 接口创建视频 job。状态来源仍以 `GET /projects/{id}` 聚合快照为主，视频历史版本通过 `GET /videos` 懒加载。UI 明确区分“草稿态”和“视频版本态”：前者管理当前待提交的 prompt/references/params，后者管理已提交成功或失败的视频版本与播放器。预览 URL 的优先级必须固定为：`currentVideoVersion.video_url` -> `storyboards.current_video_url` -> `generationQueue.video_url`，这样页面刷新后即使 queue 行消失也能恢复当前可播放视频。

**Tech Stack:** Vue 3.5 `<script setup>` / TypeScript 5.7 / Pinia 2 / Axios / Vitest / @vue/test-utils。

---

## References

- Current generation panel:
  - `frontend/src/components/generation/GenerationPanel.vue`
  - `frontend/src/components/generation/RenderVersionHistory.vue`
  - `frontend/src/components/generation/RenderRetryBanner.vue`
- Current store/API types:
  - `frontend/src/store/workbench.ts`
  - `frontend/src/api/shots.ts`
  - `frontend/src/types/api.ts`
  - `frontend/src/types/index.ts`
- Approved product rules from this thread:
  - keep `生成草稿`
  - final generation is video, not image
  - prompt must pass through raw
  - references must pass through raw
  - user-selectable params: duration / resolution / model_type

## Scope

**Includes:**

- Keep `生成草稿`
- Replace `确认生成` with `生成视频`
- Add three parameter selectors:
  - 视频时长
  - 分辨率
  - 模型类型
- Replace image-only preview with video-first preview
- Load and switch video history versions
- Keep current image draft references UI
- Update store to track video jobs and version history
- Update unit tests for panel/store/api types

**Excludes:**

- Removing `render-draft`
- Batch continue generate
- Multi-shot orchestration
- Audio toggle UI
- Export panel integration

## UX Rules

- `生成草稿` continues to fetch recommended prompt + references
- `生成视频` submits the current textarea content exactly as typed
- `生成视频` submits the current references exactly as listed
- No hidden prompt rewrite
- No suffix/prefix appended by frontend
- Right panel is `Video Preview`, not `Frame Preview`
- If a previous successful video exists and a new job is running, keep showing the old successful video while displaying “新版本生成中”
- Prompt textarea is a real source of truth, not a delayed local shadow copy:
  - `@input` must immediately patch the draft in store, or submit must read the latest local draft state from the same source
  - do not allow `generateVideo()` to submit stale prompt text
- Reuse `RenderVersionHistory.vue` as the single version-history modal for video in this flow; do not create a second modal component on the first pass

## File Structure

**Modify:**

```text
frontend/src/api/shots.ts
frontend/src/components/generation/GenerationPanel.vue
frontend/src/components/generation/RenderVersionHistory.vue
frontend/src/store/workbench.ts
frontend/src/types/api.ts
frontend/src/types/index.ts
frontend/tests/unit/generation.panel.spec.ts
frontend/tests/unit/workbench.m3b.store.spec.ts
frontend/tests/unit/shots.api.spec.ts
frontend/README.md
```

## Task 1: Add API and type contract for shot final video

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/shots.ts`
- Modify: `frontend/tests/unit/shots.api.spec.ts`

- [ ] **Step 1: Write failing API test**

Add to `frontend/tests/unit/shots.api.spec.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { shotsApi } from "@/api/shots";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    post: vi.fn(),
    get: vi.fn()
  }
}));

describe("shotsApi video", () => {
  it("generateVideo(): posts raw prompt, references, and params", async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: { job_id: "JOB1", sub_job_ids: [] } } as never);

    const payload = {
      prompt: "原样提示词",
      references: [{ id: "scene:1", kind: "scene", source_id: "S1", name: "东宫", image_url: "https://example.com/1.png" }],
      duration: 5,
      resolution: "720p" as const,
      model_type: "fast" as const
    };

    const ack = await shotsApi.generateVideo("P1", "SH1", payload);

    expect(client.post).toHaveBeenCalledWith("/projects/P1/shots/SH1/video", payload, { timeout: 60000 });
    expect(ack.job_id).toBe("JOB1");
  });
});
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/shots.api.spec.ts
```

Expected: FAIL because `generateVideo` and new payload types do not exist.

- [ ] **Step 3: Extend API types**

In `frontend/src/types/api.ts`, keep existing render-draft types and add:

```ts
export const SHOT_VIDEO_DURATION_PRESETS = [4, 5, 8, 10] as const;
export type ShotVideoDurationPreset = (typeof SHOT_VIDEO_DURATION_PRESETS)[number];
export type ShotVideoResolution = "480p" | "720p";
export type ShotVideoModelType = "standard" | "fast";

export interface ShotVideoSubmitRequest {
  prompt: string;
  references: RenderSubmitReference[];
  duration: number;
  resolution: ShotVideoResolution;
  model_type: ShotVideoModelType;
}

export interface ShotVideoVersionRead {
  id: string;
  shot_id: string;
  version_no: number;
  status: string;
  prompt_snapshot: Record<string, unknown> | null;
  params_snapshot: Record<string, unknown> | null;
  video_url: string | null;
  last_frame_url: string | null;
  provider_task_id: string | null;
  error_code: string | null;
  error_msg: string | null;
  created_at: string;
  finished_at: string | null;
  is_current: boolean;
}

export interface ShotVideoVersionSelectResponse {
  shot_id: string;
  current_video_render_id: string | null;
  status: string;
}
```

Also extend storyboard detail:

```ts
current_video_render_id: string | null;
current_video_url: string | null;
current_last_frame_url: string | null;
current_video_version_no: number | null;
current_video_params_snapshot: Record<string, unknown> | null;
```

And extend aggregated queue row with:

```ts
video_render_id?: string | null;
video_url?: string | null;
last_frame_url?: string | null;
params_snapshot?: Record<string, unknown> | null;
```

UI should offer only the preset buttons in `SHOT_VIDEO_DURATION_PRESETS`, but the request type stays `number` so frontend stays compatible with the backend's `[4,15]` validation contract.

- [ ] **Step 4: Extend view-model types**

In `frontend/src/types/index.ts` add:

```ts
export interface VideoGenerationDraft {
  prompt: string;
  references: RenderSubmitReference[];
  duration: ShotVideoDurationPreset;
  resolution: ShotVideoResolution;
  modelType: ShotVideoModelType;
}

export interface VideoShotItem {
  shotId: string;
  title: string;
  summary: string;
  shotStatus: string;
  status: RenderStatus;
  progress: number;
  currentVideoRenderId: string | null;
  videoUrl: string | null;
  lastFrameUrl: string | null;
  versionNo: number | null;
  activeJobId: string | null;
  errorCode: string | null;
  errorMsg: string | null;
  paramsSnapshot: Record<string, unknown> | null;
}
```

- [ ] **Step 5: Extend shots API client**

Modify `frontend/src/api/shots.ts`:

```ts
  async generateVideo(
    projectId: string,
    shotId: string,
    payload: ShotVideoSubmitRequest
  ): Promise<GenerateJobAck> {
    const r = await client.post(
      `/projects/${projectId}/shots/${shotId}/video`,
      payload,
      { timeout: RENDER_TIMEOUT_MS }
    );
    return r.data;
  },

  async listVideos(projectId: string, shotId: string): Promise<ShotVideoVersionRead[]> {
    const r = await client.get(`/projects/${projectId}/shots/${shotId}/videos`);
    return r.data;
  },

  async selectVideo(projectId: string, shotId: string, videoId: string): Promise<ShotVideoVersionSelectResponse> {
    const r = await client.post(`/projects/${projectId}/shots/${shotId}/videos/${videoId}/select`);
    return r.data;
  },
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/shots.api.spec.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types frontend/src/api/shots.ts frontend/tests/unit/shots.api.spec.ts
git commit -m "feat(frontend): add shot final video api contract"
```

## Task 2: Rework store from image-render job tracking to video job tracking

**Files:**
- Modify: `frontend/src/store/workbench.ts`
- Modify: `frontend/tests/unit/workbench.m3b.store.spec.ts`

Reuse the existing `frontend/tests/unit/workbench.m3b.store.spec.ts`; do not rename or duplicate it.

- [ ] **Step 1: Write failing store test**

Add to `frontend/tests/unit/workbench.m3b.store.spec.ts`:

```ts
it("generateVideoFromDraft(): stores active video job and selected params", async () => {
  const store = useWorkbenchStore();
  store.current = structuredClone(projectFixture) as never;
  store.selectedShotId = "SH1";
  store.updateRenderDraft("SH1", {
    shot_id: "SH1",
    prompt: "原样提示词",
    references: [{ id: "scene:1", kind: "scene", source_id: "S1", name: "东宫", image_url: "https://example.com/1.png" }]
  });
  store.setVideoDraftOptions("SH1", { duration: 5, resolution: "720p", modelType: "fast" });

  vi.spyOn(shotsApi, "generateVideo").mockResolvedValue({ job_id: "JOB1", sub_job_ids: [] });

  await store.generateVideoFromDraft("SH1");

  expect(store.activeRenderJobId).toBe("JOB1");
  expect(store.activeRenderShotId).toBe("SH1");
});
```

- [ ] **Step 2: Run the failing store test**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/workbench.m3b.store.spec.ts
```

Expected: FAIL because `setVideoDraftOptions` / `generateVideoFromDraft` do not exist.

- [ ] **Step 3: Add dedicated video draft state**

In `frontend/src/store/workbench.ts` keep `renderDrafts` for prompt+references, and add:

```ts
const videoDraftOptions = ref<Record<string, {
  duration: ShotVideoDurationPreset;
  resolution: ShotVideoResolution;
  modelType: ShotVideoModelType;
}>>({});

const videoVersions = ref<Record<string, ShotVideoVersionRead[]>>({});
```

Default options helper:

```ts
function ensureVideoDraftOptions(shotId: string) {
  if (!videoDraftOptions.value[shotId]) {
    videoDraftOptions.value[shotId] = {
      duration: 5,
      resolution: "720p",
      modelType: "fast"
    };
  }
  return videoDraftOptions.value[shotId];
}
```

- [ ] **Step 4: Add store actions**

Implement:

```ts
function videoDraftOptionsFor(shotId: string) {
  return ensureVideoDraftOptions(shotId);
}

function setVideoDraftOptions(
  shotId: string,
  patch: Partial<{ duration: ShotVideoDurationPreset; resolution: ShotVideoResolution; modelType: ShotVideoModelType; }>
) {
  videoDraftOptions.value[shotId] = { ...ensureVideoDraftOptions(shotId), ...patch };
}

async function generateVideoFromDraft(shotId: string): Promise<string> {
  if (!current.value) throw new Error("generateVideoFromDraft: no current project");
  if (activeRenderJobId.value) throw new Error("已有镜头视频任务进行中");
  const draft = renderDrafts.value[shotId];
  if (!draft?.prompt?.trim()) throw new Error("请先生成或填写镜头提示词");
  if (!draft.references.length) throw new Error("至少保留 1 张参考图后才能生成视频");

  const options = ensureVideoDraftOptions(shotId);
  const ack = await shotsApi.generateVideo(current.value.id, shotId, {
    prompt: draft.prompt,
    references: draft.references.map(({ id, kind, source_id, name, image_url }) => ({ id, kind, source_id, name, image_url })),
    duration: options.duration,
    resolution: options.resolution,
    model_type: options.modelType,
  });
  renderError.value = null;
  renderJob.value = { projectId: current.value.id, jobId: ack.job_id, shotId };
  return ack.job_id;
}
```

- [ ] **Step 5: Switch history loading to video versions**

Replace:

```ts
fetchRenderVersions
renderVersionsFor
selectRenderVersion
```

with:

```ts
fetchVideoVersions
videoVersionsFor
selectVideoVersion
```

Each one should call the new `shotsApi.listVideos` / `shotsApi.selectVideo`.

- [ ] **Step 6: Update computed shot list to use video queue**

Keep the public computed name `renderShots` for the first pass to avoid cross-component churn, but make each row video-aware and prefer `render_shot_video` queue rows:

```ts
const renderShots = computed<VideoShotItem[]>(() =>
  (current.value?.storyboards ?? []).map((shot) => {
    const queue = (current.value?.generationQueue ?? []).find(
      (item) =>
        item.kind === "render_shot_video" &&
        (item.target_id === shot.id || item.shot_id === shot.id || item.video_render_id === shot.current_video_render_id)
    );
    ...
  })
);
```

Use:

```ts
currentVideoRenderId: shot.current_video_render_id,
videoUrl: shot.current_video_url ?? queue?.video_url ?? null,
lastFrameUrl: shot.current_last_frame_url ?? queue?.last_frame_url ?? null,
versionNo: shot.current_video_version_no ?? queue?.version_no ?? null,
paramsSnapshot: queue?.params_snapshot ?? null,
```

- [ ] **Step 7: Run store tests**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/workbench.m3b.store.spec.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/store/workbench.ts frontend/tests/unit/workbench.m3b.store.spec.ts
git commit -m "feat(frontend): track shot final video jobs in store"
```

## Task 3: Replace confirm-render UI with generate-video UI

**Files:**
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Modify: `frontend/tests/unit/generation.panel.spec.ts`

- [ ] **Step 1: Write failing panel tests**

Add to `frontend/tests/unit/generation.panel.spec.ts`:

```ts
it("shows duration, resolution, and model selectors", () => {
  const wrapper = mountPanel();
  expect(wrapper.text()).toContain("视频时长");
  expect(wrapper.text()).toContain("分辨率");
  expect(wrapper.text()).toContain("模型类型");
});

it("replaces confirm button with generate video", () => {
  const wrapper = mountPanel();
  expect(wrapper.text()).toContain("生成视频");
  expect(wrapper.text()).not.toContain("确认生成");
});

it("shows Video Preview when current version has video", async () => {
  const wrapper = mountPanel({
    currentVersion: {
      id: "VID1",
      shot_id: "SH1",
      version_no: 1,
      status: "succeeded",
      prompt_snapshot: null,
      params_snapshot: null,
      video_url: "https://example.com/out.mp4",
      last_frame_url: "https://example.com/out.png",
      provider_task_id: "cgt-1",
      error_code: null,
      error_msg: null,
      created_at: "2026-04-23T12:00:00Z",
      finished_at: "2026-04-23T12:01:00Z",
      is_current: true
    }
  });
  expect(wrapper.text()).toContain("Video Preview");
  expect(wrapper.find("video").exists()).toBe(true);
});
```

- [ ] **Step 2: Run the failing panel tests**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/generation.panel.spec.ts
```

Expected: FAIL because panel still renders image-confirm flow.

- [ ] **Step 3: Add parameter selector state bindings**

In `GenerationPanel.vue`, replace the old confirm button path:

```ts
const selectedDraft = computed(() =>
  selectedRenderShot.value ? store.renderDraftFor(selectedRenderShot.value.shotId) : null
);

const selectedVideoOptions = computed(() =>
  selectedRenderShot.value ? store.videoDraftOptionsFor(selectedRenderShot.value.shotId) : null
);

const currentVideoVersion = computed(() =>
  selectedRenderShot.value
    ? store.videoVersionsFor(selectedRenderShot.value.shotId).find((item) => item.is_current) ?? null
    : null
);

const currentParams = computed(() => {
  if (currentVideoVersion.value?.params_snapshot) {
    return toVideoParamSummary(currentVideoVersion.value.params_snapshot);
  }
  return selectedRenderShot.value ? store.videoDraftOptionsFor(selectedRenderShot.value.shotId) : null;
});

const generateVideoDisabled = computed(() => {
  if (!selectedRenderShot.value || !selectedDraft.value) return true;
  const isActiveShot =
    activeRenderJobId.value && activeRenderShotId.value === selectedRenderShot.value.shotId;
  return isActiveShot || !selectedDraft.value.prompt.trim() || selectedDraft.value.references.length === 0;
});

function toVideoParamSummary(snapshot: Record<string, unknown>) {
  return {
    duration: Number(snapshot.duration ?? 5),
    resolution: String(snapshot.resolution ?? "720p") as ShotVideoResolution,
    modelType: String(snapshot.model_type ?? "fast") as ShotVideoModelType,
  };
}
```

Setter helpers:

```ts
function setDuration(duration: ShotVideoDurationPreset) {
  if (!selectedRenderShot.value) return;
  store.setVideoDraftOptions(selectedRenderShot.value.shotId, { duration });
}

function setResolution(resolution: ShotVideoResolution) {
  if (!selectedRenderShot.value) return;
  store.setVideoDraftOptions(selectedRenderShot.value.shotId, { resolution });
}

function setModelType(modelType: ShotVideoModelType) {
  if (!selectedRenderShot.value) return;
  store.setVideoDraftOptions(selectedRenderShot.value.shotId, { modelType });
}
```

- [ ] **Step 4: Replace confirm action**

Replace `confirmRender` with:

```ts
async function generateVideo() {
  if (!selectedRenderShot.value || generateVideoDisabled.value) return;
  submitting.value = true;
  try {
    await store.generateVideoFromDraft(selectedRenderShot.value.shotId);
    toast.info("已提交视频生成任务");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "视频生成失败");
  } finally {
    submitting.value = false;
  }
}
```

Button label:

```ts
const generateVideoButtonText = computed(() => {
  if (submitting.value || (activeRenderJobId.value && activeRenderShotId.value === selectedRenderShot.value?.shotId)) {
    return "视频生成中...";
  }
  return currentVideoVersion.value?.video_url ? "重新生成视频" : "生成视频";
});
```

Prompt editing must not rely on a stale shadow copy:

```ts
function onPromptInput(value: string) {
  if (!selectedRenderShot.value || !selectedDraft.value) return;
  store.updateRenderDraft(selectedRenderShot.value.shotId, { prompt: value });
}
```

- [ ] **Step 5: Replace preview area**

Replace image preview block with:

```vue
<div class="preview-frame">
  <div class="frame-caption">
    <span>Video Preview</span>
    <strong>{{ selectedRenderShot.title }}</strong>
  </div>
  <video
    v-if="previewVideoUrl"
    class="preview-video"
    :src="previewVideoUrl"
    controls
    playsinline
    preload="metadata"
  />
  <div v-else-if="activeRenderJobId && activeRenderShotId === selectedRenderShot.shotId" class="preview-empty">
    正在生成成品视频，请稍候
  </div>
  <div v-else class="preview-empty">
    当前还没有可播放的成品视频
  </div>
</div>
<RenderRetryBanner
  v-if="showVideoGeneratingBanner"
  title="新版本生成中"
  message="继续展示当前成功版本，新的成品视频完成后会自动刷新。"
/>
```

`previewVideoUrl`:

```ts
const previewVideoUrl = computed(
  () =>
    currentVideoVersion.value?.video_url ??
    selectedRenderShot.value?.videoUrl ??
    null
);

const showVideoGeneratingBanner = computed(() =>
  Boolean(
    previewVideoUrl.value &&
    activeRenderJobId.value &&
    activeRenderShotId.value === selectedRenderShot.value?.shotId
  )
);
```

- [ ] **Step 6: Show parameter summary under preview**

Use either current version `params_snapshot` or selected draft options:

```vue
<article>
  <span>当前参数</span>
  <dl class="param-summary">
    <div><dt>时长</dt><dd>{{ currentParams.duration }} 秒</dd></div>
    <div><dt>分辨率</dt><dd>{{ currentParams.resolution }}</dd></div>
    <div><dt>模型</dt><dd>{{ currentParams.modelType === "fast" ? "极速" : "标准" }}</dd></div>
  </dl>
</article>
```

- [ ] **Step 7: Run panel tests**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/generation.panel.spec.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/generation/GenerationPanel.vue frontend/tests/unit/generation.panel.spec.ts
git commit -m "feat(frontend): switch generation panel to final video flow"
```

## Task 4: Update version history and job polling behavior

**Files:**
- Modify: `frontend/src/components/generation/RenderVersionHistory.vue`
- Modify: `frontend/src/components/generation/RenderRetryBanner.vue`
- Modify: `frontend/src/store/workbench.ts`
- Modify: `frontend/tests/unit/generation.panel.spec.ts`

- [ ] **Step 1: Write failing history test**

Add:

```ts
it("history modal lists video versions with playable status", async () => {
  const wrapper = mountPanelWithVideoHistory();
  await wrapper.find("button").filter((b) => b.text() === "查看历史版本")[0].trigger("click");
  expect(wrapper.text()).toContain("版本 v2");
  expect(wrapper.text()).toContain("已完成");
});
```

Define `mountPanelWithVideoHistory()` in the spec file next to `mountPanel()`; do not assume it already exists.

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/generation.panel.spec.ts
```

Expected: FAIL if the history component still assumes image versions.

- [ ] **Step 3: Update history component**

Repurpose `RenderVersionHistory.vue` as the single history modal for this flow. Update labels from image-centric wording to version-neutral wording and use `ShotVideoVersionRead`.

Minimal prop change:

```ts
const props = defineProps<{
  versions: ShotVideoVersionRead[];
  currentRenderId: string | null;
  ...
}>();
```

Row metadata should display:

- version number
- status
- created_at
- current tag
- lightweight preview player for the highlighted history row: `<video preload="none" controls>`

Do not auto-select a historical version just to preview it; previewing inside the modal must not mutate current selection until the user clicks the explicit switch action.

- [ ] **Step 4: Update polling success path**

In store/panel polling success path:

```ts
await store.reload();
store.markRenderSucceeded();
if (shotId) await store.fetchVideoVersions(shotId);
toast.success("视频生成完成");
```

Error path:

```ts
const msg =
  j?.error_msg ??
  (err instanceof ApiError ? messageFor(err.code, err.message) : "视频生成失败");
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd frontend
npm run test -- --run tests/unit/generation.panel.spec.ts tests/unit/workbench.m3b.store.spec.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/generation/RenderVersionHistory.vue frontend/src/components/generation/RenderRetryBanner.vue frontend/src/store/workbench.ts
git commit -m "feat(frontend): load and switch shot final video versions"
```

## Task 5: Final verification and docs

**Files:**
- Modify: `frontend/README.md`

- [ ] **Step 1: Update README**

Document:

- `生成草稿` now recommends prompt + references
- final generation is video, not image
- exposed parameter choices:
  - duration
  - resolution
  - model type
- required backend endpoints:
  - `POST /render-draft`
  - `POST /video`
  - `GET /videos`
  - `POST /videos/{id}/select`

- [ ] **Step 2: Run end-to-end frontend checks**

Run:

```bash
cd frontend
npm run typecheck
npm run test -- --run tests/unit/shots.api.spec.ts tests/unit/workbench.m3b.store.spec.ts tests/unit/generation.panel.spec.ts
```

Expected: PASS.

- [ ] **Step 3: Manual smoke checklist**

With local services running:

1. Open `http://localhost:5173/projects/<project-id>`
2. Select a shot in the generation panel
3. Click `生成草稿`
4. Confirm prompt textarea fills in
5. Confirm references appear
6. Toggle:
   - `视频时长`
   - `分辨率`
   - `模型类型`
7. Click `生成视频`
8. Confirm button changes to `视频生成中...`
9. Confirm right panel eventually shows a `<video>` player
10. Open `查看历史版本` and switch to an older successful version

- [ ] **Step 4: Commit**

```bash
git add frontend/README.md
git commit -m "docs(frontend): document shot final video workflow"
```

## Self-Review Checklist

- The plan keeps `生成草稿`
- The plan removes `确认生成`
- The plan adds duration/resolution/model type selectors
- The plan keeps prompt and references raw
- The plan upgrades preview from image-only to video-first
- The plan preserves historical version switching and final lock semantics
