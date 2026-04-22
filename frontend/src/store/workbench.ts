/* frontend/src/store/workbench.ts */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { projectsApi } from "@/api/projects";
import { storyboardsApi } from "@/api/storyboards";
import { charactersApi } from "@/api/characters";
import { scenesApi } from "@/api/scenes";
import { shotsApi } from "@/api/shots";
import { ApiError } from "@/utils/error";
import type { ProjectData, RenderShotItem, RenderStatus } from "@/types";
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
  SceneUpdate,
  JobState,
  RenderDraftRead,
  RenderSubmitRequest,
  RenderVersionRead
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

  // ---- job 追踪(均按 projectId 作用域) ----
  const parseJob = ref<{ projectId: string; jobId: string } | null>(null);
  const genStoryboardJob = ref<{ projectId: string; jobId: string } | null>(null);
  const parseError = ref<string | null>(null);

  const generateCharactersJob = ref<{ projectId: string; jobId: string } | null>(null);
  const generateCharactersError = ref<string | null>(null);

  const generateScenesJob = ref<{ projectId: string; jobId: string } | null>(null);
  const generateScenesError = ref<string | null>(null);

  const lockCharacterJob = ref<{ projectId: string; jobId: string; characterId: string } | null>(null);
  const lockCharacterError = ref<string | null>(null);

  const lockSceneJob = ref<{ projectId: string; jobId: string; sceneId: string } | null>(null);
  const lockSceneError = ref<string | null>(null);
  const renderJob = ref<{ projectId: string; jobId: string; shotId: string } | null>(null);
  const renderError = ref<string | null>(null);
  const renderDrafts = ref<Record<string, RenderDraftRead>>({});
  const renderVersions = ref<Record<string, RenderVersionRead[]>>({});
  const renderHistoryLoadingShotId = ref<string | null>(null);

  // 单项 regen: key = "<kind>:<id>"; value = jobId
  const regenJobs = ref<Record<string, { projectId: string; jobId: string }>>({});

  function scopedJobId(
    scope: { projectId: string; jobId: string } | null
  ): string | null {
    if (!scope || !current.value || scope.projectId !== current.value.id) return null;
    return scope.jobId;
  }

  const activeParseJobId = computed<string | null>(() => scopedJobId(parseJob.value));
  const activeGenStoryboardJobId = computed<string | null>(() => scopedJobId(genStoryboardJob.value));
  const activeGenerateCharactersJobId = computed<string | null>(() =>
    scopedJobId(generateCharactersJob.value)
  );
  const activeGenerateScenesJobId = computed<string | null>(() =>
    scopedJobId(generateScenesJob.value)
  );
  const activeLockCharacterJobId = computed<string | null>(() =>
    current.value && lockCharacterJob.value && lockCharacterJob.value.projectId === current.value.id
      ? lockCharacterJob.value.jobId
      : null
  );
  const activeLockCharacterId = computed<string | null>(() =>
    lockCharacterJob.value && current.value && lockCharacterJob.value.projectId === current.value.id
      ? lockCharacterJob.value.characterId : null
  );

  const activeLockSceneJobId = computed<string | null>(() =>
    current.value && lockSceneJob.value && lockSceneJob.value.projectId === current.value.id
      ? lockSceneJob.value.jobId
      : null
  );
  const activeLockSceneId = computed<string | null>(() =>
    lockSceneJob.value && current.value && lockSceneJob.value.projectId === current.value.id
      ? lockSceneJob.value.sceneId : null
  );
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

  function mapJobStatusToRenderStatus(
    status?: string | null,
    shotStatus?: string | null
  ): RenderStatus {
    if (status === "queued" || status === "running") return "processing";
    if (status === "failed" || status === "canceled") return "failed";
    if (status === "succeeded") return "success";
    if (shotStatus === "failed") return "failed";
    if (shotStatus === "generating") return "processing";
    return "success";
  }

  const renderShots = computed<RenderShotItem[]>(() =>
    (current.value?.storyboards ?? []).map((shot) => {
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
        status: mapJobStatusToRenderStatus(queue?.status, queue?.shot_status ?? shot.status),
        progress:
          queue?.progress ??
          (shot.status === "failed" ? 0 : shot.status === "generating" ? 1 : 100),
        currentRenderId: shot.current_render_id,
        imageUrl: queue?.image_url ?? null,
        versionNo: queue?.version_no ?? null,
        activeJobId: isActive ? activeRenderJobId.value : null,
        errorCode: queue?.error_code ?? null,
        errorMsg: queue?.error_msg ?? (shot.status === "failed" ? renderError.value : null)
      };
    })
  );

  // ---- 核心 load/reload/rollback ----
  async function load(id: string) {
    loading.value = true;
    error.value = null;
    try {
      const shouldResetRenderState = current.value?.id !== id;
      current.value = await projectsApi.get(id);
      if (shouldResetRenderState) {
        renderDrafts.value = {};
        renderVersions.value = {};
        renderJob.value = null;
        renderError.value = null;
      }
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

  async function findAndTrackGenStoryboardJob() {
    if (!current.value) return;
    const jobs = await projectsApi.getJobs(current.value.id);
    const gsJob = jobs.find(
      (j: JobState) =>
        j.kind === "gen_storyboard" && (j.status === "queued" || j.status === "running")
    );
    if (gsJob) {
      genStoryboardJob.value = { projectId: current.value.id, jobId: gsJob.id };
    }
  }

  /**
   * I2: 刷新页面时,按当前阶段找回正在运行的任务 (gen_characters / gen_scenes / register_character_asset)
   * I3: 同时也找回最近一个失败的任务,以便显示错误提示
   */
  async function findAndTrackActiveJobs() {
    if (!current.value) return;
    const stage = current.value.stage_raw;

    // 只有在特定阶段且没有数据时才找回,避免误报
    if (stage === "draft") {
      await findAndTrackGenStoryboardJob();
    } else {
      const jobs = await projectsApi.getJobs(current.value.id);
      const running = (kind: string) =>
        jobs.find(
          (j: JobState) =>
            j.kind === kind && (j.status === "queued" || j.status === "running")
        );

      const lastFailed = (kind: string) =>
        jobs
          .filter((j: JobState) => j.kind === kind && j.status === "failed")
          .sort(
            (a, b) =>
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          )[0];

      if (stage === "storyboard_ready") {
        const gcJob = running("gen_character_asset");
        if (gcJob) {
          generateCharactersJob.value = { projectId: current.value.id, jobId: gcJob.id };
        } else {
          const failed = lastFailed("gen_character_asset");
          if (failed) generateCharactersError.value = failed.error_msg;
        }

        const lcaJob = running("register_character_asset");
        if (lcaJob) {
          const cid = (lcaJob.payload as { character_id?: string } | null)?.character_id ?? "";
          lockCharacterJob.value = {
            projectId: current.value.id,
            jobId: lcaJob.id,
            characterId: cid
          };
        } else {
          const failed = lastFailed("register_character_asset");
          if (failed) lockCharacterError.value = failed.error_msg;
        }
      } else if (stage === "characters_locked") {
        const gsJob = running("gen_scene_asset");
        if (gsJob) {
          generateScenesJob.value = { projectId: current.value.id, jobId: gsJob.id };
        } else {
          const failed = lastFailed("gen_scene_asset");
          if (failed) generateScenesError.value = failed.error_msg;
        }

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
      }

      if (stage === "scenes_locked" || stage === "rendering" || stage === "ready_for_export") {
        const rJob = running("render_shot");
        if (rJob) {
          const shotId =
            rJob.target_id ??
            ((rJob.payload as { shot_id?: string } | null)?.shot_id ?? "") ??
            "";
          renderJob.value = { projectId: current.value.id, jobId: rJob.id, shotId };
        } else {
          renderJob.value = null;
          const failed = lastFailed("render_shot");
          if (failed) renderError.value = failed.error_msg;
        }
      }
    }
  }

  function markGenStoryboardSucceeded() { genStoryboardJob.value = null; }
  function markGenStoryboardFailed(msg: string) { genStoryboardJob.value = null; parseError.value = msg; }

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
      throw new Error("已有角色重生成任务进行中");
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
    lockCharacterError.value = null;
    const resp = await charactersApi.lock(current.value.id, characterId, payload);
    if (resp.ack === "async") {
      lockCharacterJob.value = { projectId: current.value.id, jobId: resp.job_id, characterId };
      return;
    }
    await reload();
  }
  function markLockCharacterSucceeded() { lockCharacterJob.value = null; lockCharacterError.value = null; }
  function markLockCharacterFailed(msg: string) { lockCharacterJob.value = null; lockCharacterError.value = msg; }

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
      throw new Error("已有场景重生成任务进行中");
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
    lockSceneError.value = null;
    const resp = await scenesApi.lock(current.value.id, sceneId, {});
    lockSceneJob.value = { projectId: current.value.id, jobId: resp.job_id, sceneId };
  }
  function markLockSceneSucceeded() { lockSceneJob.value = null; lockSceneError.value = null; }
  function markLockSceneFailed(msg: string) { lockSceneJob.value = null; lockSceneError.value = msg; }

  async function bindShotScene(shotId: string, sceneId: string) {
    if (!current.value) throw new Error("bindShotScene: no current project");
    await storyboardsApi.bindScene(current.value.id, shotId, { scene_id: sceneId });
    await reload();
  }

  async function fetchRenderDraft(shotId: string): Promise<RenderDraftRead> {
    if (!current.value) throw new Error("fetchRenderDraft: no current project");
    const draft = await shotsApi.renderDraft(current.value.id, shotId);
    renderDrafts.value[shotId] = draft;
    return draft;
  }

  function renderDraftFor(shotId: string): RenderDraftRead | null {
    return renderDrafts.value[shotId] ?? null;
  }

  function updateRenderDraft(shotId: string, patch: Partial<RenderDraftRead>) {
    const currentDraft = renderDrafts.value[shotId];
    if (!currentDraft) return;
    renderDrafts.value[shotId] = { ...currentDraft, ...patch };
  }

  async function confirmRenderShot(shotId: string, payload: RenderSubmitRequest): Promise<string> {
    if (!current.value) throw new Error("renderShot: no current project");
    if (activeRenderJobId.value) throw new Error("已有镜头渲染任务进行中");
    renderError.value = null;
    const ack = await shotsApi.render(current.value.id, shotId, payload);
    renderJob.value = { projectId: current.value.id, jobId: ack.job_id, shotId };
    return ack.job_id;
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
    activeParseJobId, activeGenStoryboardJobId, parseError,
    activeGenerateCharactersJobId, generateCharactersError,
    activeGenerateScenesJobId, generateScenesError,
    regenJobIdFor, activeRegenJobEntries,
    currentShot, selectedCharacter, selectedScene,
    load, reload, rollback,
    startParse, markParseSucceeded, markParseFailed,
    findAndTrackGenStoryboardJob, findAndTrackActiveJobs,
    markGenStoryboardSucceeded, markGenStoryboardFailed,
    createShot, updateShot, deleteShot, reorderShots, moveShotUp, moveShotDown, confirmStoryboards,
    generateCharacters, markGenerateCharactersSucceeded, markGenerateCharactersFailed,
    patchCharacter, regenerateCharacter, lockCharacter,
    generateScenes, markGenerateScenesSucceeded, markGenerateScenesFailed,
    patchScene, regenerateScene, lockScene, bindShotScene,
    activeLockCharacterJobId, activeLockCharacterId, lockCharacterError,
    markLockCharacterSucceeded, markLockCharacterFailed,
    activeLockSceneJobId, activeLockSceneId, lockSceneError,
    markLockSceneSucceeded, markLockSceneFailed,
    fetchRenderDraft, renderDraftFor, updateRenderDraft,
    confirmRenderShot, fetchRenderVersions, renderVersionsFor,
    selectRenderVersion, lockShot, markRenderSucceeded, markRenderFailed,
    renderShots, activeRenderJobId, activeRenderShotId,
    renderHistoryLoadingShotId, renderError,
    markRegenByKeySucceeded, markRegenByKeyFailed,
    selectShot, selectCharacter, selectScene, setStep
  };
});
