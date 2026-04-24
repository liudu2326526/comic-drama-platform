import { computed, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/projects", () => ({
  projectsApi: {
    get: vi.fn(),
    getJobs: vi.fn()
  }
}));

vi.mock("@/api/characters", () => ({
  charactersApi: {
    generate: vi.fn()
  }
}));

const generatePollingJob = ref<any>(null);
const noopPollingJob = ref<any>(null);
let generatePollingHandlers: any = null;

vi.mock("@/composables/useJobPolling", () => ({
  useJobPolling: (jobId: unknown, handlers: unknown) => {
    const currentJobId =
      typeof jobId === "object" && jobId !== null && "value" in jobId
        ? (jobId as { value: unknown }).value
        : jobId;
    if (currentJobId) {
      generatePollingHandlers = handlers;
      return { job: generatePollingJob, cancel: vi.fn() };
    }
    return { job: noopPollingJob, cancel: vi.fn() };
  }
}));

vi.mock("@/composables/useStageGate", () => ({
  useStageGate: () => ({
    flags: computed(() => ({
      canGenerateCharacters: true,
      canEditCharacters: true,
      canLockCharacter: true,
      canRegisterCharacterAsset: true,
      canConfirmCharacters: true
    }))
  })
}));

vi.mock("@/composables/useToast", () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  })
}));

vi.mock("@/composables/useConfirm", () => ({
  confirm: vi.fn().mockResolvedValue(true)
}));

import CharacterAssetsPanel from "@/components/character/CharacterAssetsPanel.vue";
import { charactersApi } from "@/api/characters";
import { projectsApi } from "@/api/projects";
import { useWorkbenchStore } from "@/store/workbench";
import type { JobState } from "@/types/api";

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

describe("character generation chain", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
    generatePollingJob.value = null;
    noopPollingJob.value = null;
    generatePollingHandlers = null;
  });

  it("prefers extract_characters over gen_character_asset when both jobs are present", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(projectsApi, "getJobs").mockResolvedValue([
      {
        id: "job-render",
        kind: "gen_character_asset",
        status: "running",
        progress: 20,
        total: 6,
        done: 1,
        payload: null,
        result: null,
        error_msg: null,
        created_at: "2026-04-23T00:00:00Z",
        finished_at: null
      },
      {
        id: "job-extract",
        kind: "extract_characters",
        status: "running",
        progress: 45,
        total: null,
        done: 0,
        payload: null,
        result: null,
        error_msg: null,
        created_at: "2026-04-23T00:00:01Z",
        finished_at: null
      }
    ] as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    await store.findAndTrackActiveJobs();

    expect(store.activeGenerateCharactersJobId).toBe("job-extract");
  });

  it("clears stale generateCharactersError when a running extract_characters job is recovered", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(projectsApi, "getJobs").mockResolvedValue([
      {
        id: "job-extract",
        kind: "extract_characters",
        status: "running",
        progress: 45,
        total: null,
        done: 0,
        payload: null,
        result: null,
        error_msg: null,
        created_at: "2026-04-23T00:00:01Z",
        finished_at: null
      }
    ] as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    store.markGenerateCharactersFailed("timeout of 60000ms exceeded");

    await store.findAndTrackActiveJobs();

    expect(store.generateCharactersError).toBeNull();
    expect(store.activeGenerateCharactersJobId).toBe("job-extract");
  });

  it("shows extract label and switches to next job when extract_characters succeeds", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(charactersApi, "generate").mockResolvedValue({
      job_id: "job-a",
      sub_job_ids: []
    } as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    await store.generateCharacters({});

    const attachSpy = vi.spyOn(store as any, "attachGenerateCharactersJob");
    const reloadSpy = vi.spyOn(store, "reload").mockResolvedValue();
    const successSpy = vi.spyOn(store, "markGenerateCharactersSucceeded");

    generatePollingJob.value = {
      id: "job-a",
      kind: "extract_characters",
      status: "running",
      progress: 45,
      total: null,
      done: 0,
      payload: null,
      result: null,
      error_msg: null,
      created_at: "",
      finished_at: null
    } satisfies JobState;

    const wrapper = mount(CharacterAssetsPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          PanelSection: { template: "<section><slot /><slot name='actions' /></section>" },
          ProgressBar: { template: "<div class='progress-bar' />" },
          CharacterEditorModal: true,
          StageRollbackModal: true
        }
      }
    });
    await flushPromises();

    expect(wrapper.text()).toContain("正在提取角色…");

    await generatePollingHandlers.onSuccess({
      id: "job-a",
      kind: "extract_characters",
      status: "succeeded",
      progress: 100,
      total: null,
      done: 0,
      payload: null,
      result: {
        next_job_id: "job-b",
        next_kind: "gen_character_asset"
      },
      error_msg: null,
      created_at: "",
      finished_at: null
    } satisfies JobState);

    expect(attachSpy).toHaveBeenCalledWith("job-b");
    expect(reloadSpy).not.toHaveBeenCalled();
    expect(successSpy).not.toHaveBeenCalled();
  });

  it("renders pending asset-library state consistently in list and action button", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      characters: [{
        id: "C1",
        name: "萧景珩",
        role: "配角",
        is_protagonist: false,
        locked: false,
        summary: "大雍东宫太子",
        description: "太子",
        meta: ["人像库:Pending"],
        reference_image_url: null
      }]
    }) as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    store.selectCharacter("C1");

    const wrapper = mount(CharacterAssetsPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          PanelSection: { template: "<section><slot name='actions' /><slot /></section>" },
          ProgressBar: { template: "<div class='progress-bar' />" },
          CharacterEditorModal: true,
          StageRollbackModal: true
        }
      }
    });
    await flushPromises();

    expect(wrapper.text()).toContain("入库中");
    const primaryButtons = wrapper.findAll("button.primary-btn");
    expect(primaryButtons.at(-1)?.text()).toBe("入库中");
    expect(primaryButtons.at(-1)?.attributes("disabled")).toBeDefined();
  });
});
