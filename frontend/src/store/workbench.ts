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
