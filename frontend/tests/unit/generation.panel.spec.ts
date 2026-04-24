import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GenerationPanel from "@/components/generation/GenerationPanel.vue";
import ReferencePickerModal from "@/components/generation/ReferencePickerModal.vue";
import { shotsApi } from "@/api/shots";
import { useWorkbenchStore } from "@/store/workbench";

const makeProject = (overrides: Partial<import("@/types").ProjectData> = {}) => ({
  id: "P1",
  name: "Demo",
  stage: "场景已匹配" as const,
  stage_raw: "scenes_locked" as const,
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
    scene_id: "SC1",
    status: "succeeded",
    current_render_id: "R1",
    current_video_render_id: "VID1",
    current_video_url: "https://example.com/current.mp4",
    current_last_frame_url: "https://example.com/current.png",
    current_video_version_no: 1,
    current_video_params_snapshot: { duration: 5, resolution: "720p", model_type: "fast" },
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
  exportTasks: [],
  ...overrides
});

function setupStore(options?: {
  currentVersion?: Record<string, unknown> | null;
  projectOverrides?: Partial<import("@/types").ProjectData>;
}) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useWorkbenchStore();
  const originalGenerateRenderDraft = store.generateRenderDraft.bind(store);
  const draft = {
    shot_id: "SH1",
    prompt: "原样提示词",
    references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img/scene.png", reason: "命中文案" }]
  };

  store.current = makeProject(options?.projectOverrides) as never;
  store.selectedShotId = "SH1";
  vi.spyOn(shotsApi, "generateRenderDraft").mockResolvedValue({ job_id: "DJ1", sub_job_ids: [] } as never);
  vi.spyOn(store, "generateRenderDraft").mockImplementation((shotId: string) => originalGenerateRenderDraft(shotId));
  vi.spyOn(store, "fetchRenderDraft").mockResolvedValue(draft as never);
  vi.spyOn(store, "renderDraftFor").mockImplementation((shotId: string) => (shotId === "SH1" ? draft : null) as never);
  vi.spyOn(store, "videoDraftOptionsFor").mockReturnValue({ duration: null, resolution: "480p", modelType: "fast" } as never);
  vi.spyOn(store, "setVideoDraftOptions").mockImplementation(() => {});
  vi.spyOn(store, "markDraftSucceeded").mockImplementation(() => {});
  vi.spyOn(store, "markDraftFailed").mockImplementation(() => {});
  vi.spyOn(store, "generateVideoFromDraft").mockResolvedValue("JOB1");
  vi.spyOn(store, "fetchVideoVersions").mockResolvedValue(
    options?.currentVersion
      ? [options.currentVersion as never]
      : []
  );
  vi.spyOn(store, "videoVersionsFor").mockReturnValue(
    options?.currentVersion ? [options.currentVersion as never] : []
  );
  vi.spyOn(store, "selectVideoVersion").mockResolvedValue();
  vi.spyOn(store, "lockShot").mockResolvedValue();

  return { pinia, store };
}

function mountPanel(options?: {
  currentVersion?: Record<string, unknown> | null;
  projectOverrides?: Partial<import("@/types").ProjectData>;
}) {
  const { pinia, store } = setupStore(options);
  const wrapper = mount(GenerationPanel, { global: { plugins: [pinia] } });
  return { wrapper, store };
}

async function mountPanelWithActiveDraftOnAnotherShot() {
  const { pinia, store } = setupStore({
    projectOverrides: {
      storyboards: [
        {
          id: "SH1",
          idx: 1,
          title: "开场",
          description: "皇城夜景",
          detail: "",
          duration_sec: 3,
          tags: [],
          scene_id: "SC1",
          status: "succeeded",
          current_render_id: "R1",
          current_video_render_id: null,
          current_video_url: null,
          current_last_frame_url: null,
          current_video_version_no: null,
          current_video_params_snapshot: null,
          created_at: "2026-04-22T00:00:00Z",
          updated_at: "2026-04-22T00:00:00Z"
        },
        {
          id: "SH3",
          idx: 3,
          title: "转场",
          description: "雨幕孤行",
          detail: "",
          duration_sec: 3,
          tags: [],
          scene_id: "SC3",
          status: "pending",
          current_render_id: null,
          current_video_render_id: null,
          current_video_url: null,
          current_last_frame_url: null,
          current_video_version_no: null,
          current_video_params_snapshot: null,
          created_at: "2026-04-22T00:00:00Z",
          updated_at: "2026-04-22T00:00:00Z"
        }
      ]
    }
  });
  await store.generateRenderDraft("SH1");
  store.selectShot("SH3");
  const wrapper = mount(GenerationPanel, { global: { plugins: [pinia] } });
  return { wrapper, store };
}

function mountPanelWithVideoHistory() {
  return mountPanel({
    currentVersion: {
      id: "VID2",
      shot_id: "SH1",
      version_no: 2,
      status: "succeeded",
      prompt_snapshot: null,
      params_snapshot: { duration: 5, resolution: "720p", model_type: "fast" },
      video_url: "https://example.com/v2.mp4",
      last_frame_url: "https://example.com/v2.png",
      provider_task_id: "cgt-2",
      error_code: null,
      error_msg: null,
      created_at: "2026-04-23T12:01:00Z",
      finished_at: "2026-04-23T12:02:00Z",
      is_current: true
    }
  });
}

function mountPanelWithFailedVersion() {
  return mountPanel({
    projectOverrides: {
      storyboards: [{
        id: "SH1",
        idx: 1,
        title: "开场",
        description: "皇城夜景",
        detail: "",
        duration_sec: 3,
        tags: [],
        scene_id: "SC1",
        status: "succeeded",
        current_render_id: "R1",
        current_video_render_id: null,
        current_video_url: null,
        current_last_frame_url: null,
        current_video_version_no: null,
        current_video_params_snapshot: null,
        created_at: "2026-04-22T00:00:00Z",
        updated_at: "2026-04-22T00:00:00Z"
      }]
    },
    currentVersion: {
      id: "VID_FAIL",
      shot_id: "SH1",
      version_no: 1,
      status: "failed",
      prompt_snapshot: null,
      params_snapshot: { duration: 5, resolution: "720p", model_type: "fast" },
      video_url: null,
      last_frame_url: null,
      provider_task_id: "cgt-fail",
      error_code: "volcano_error",
      error_msg: "MissingParameter",
      created_at: "2026-04-23T12:00:00Z",
      finished_at: "2026-04-23T12:01:00Z",
      is_current: true
    }
  });
}

describe("GenerationPanel", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("shows duration, resolution, and model selectors", async () => {
    const { wrapper } = mountPanel();
    await flushPromises();
    expect(wrapper.text()).toContain("视频时长");
    expect(wrapper.text()).toContain("分辨率");
    expect(wrapper.text()).toContain("模型类型");
    const durationButtons = wrapper.findAll('[data-testid="duration-option"]');
    expect(durationButtons.some((button) => button.classes("active"))).toBe(false);
    expect(wrapper.get('[data-testid="resolution-480p"]').classes("active")).toBe(true);
  });

  it("replaces confirm button with generate video", async () => {
    const { wrapper } = mountPanel();
    await flushPromises();
    expect(wrapper.text()).toContain("生成视频");
    expect(wrapper.text()).not.toContain("确认生成");
  });

  it("submits generate draft as an async job", async () => {
    const { wrapper, store } = mountPanel();
    await flushPromises();
    await wrapper.get('[data-testid="generate-draft-btn"]').trigger("click");
    expect(store.generateRenderDraft).toHaveBeenCalledWith("SH1");
  });

  it("saves current prompt and references before generating draft", async () => {
    const { wrapper, store } = mountPanel();
    await flushPromises();
    const updateSpy = vi.spyOn(store, "updateRenderDraft");
    const textarea = wrapper.get<HTMLTextAreaElement>('[data-testid="draft-prompt"]');

    await textarea.setValue("生成前编辑过的提示词");
    updateSpy.mockClear();
    await wrapper.get('[data-testid="generate-draft-btn"]').trigger("click");

    expect(updateSpy).toHaveBeenCalledWith("SH1", {
      prompt: "生成前编辑过的提示词",
      references: expect.arrayContaining([
        expect.objectContaining({ id: "scene-1", name: "长安殿" }),
      ]),
    });
    expect(store.generateRenderDraft).toHaveBeenCalledWith("SH1");
  });

  it("allows generating draft on another shot while a different draft job is running", async () => {
    const { wrapper, store } = await mountPanelWithActiveDraftOnAnotherShot();
    await flushPromises();

    const button = wrapper.get('[data-testid="generate-draft-btn"]');
    expect(button.attributes("disabled")).toBeUndefined();

    await button.trigger("click");
    expect(store.generateRenderDraft).toHaveBeenCalledTimes(2);
    expect(store.generateRenderDraft).toHaveBeenLastCalledWith("SH3");
  });

  it("submits generate video from the current draft", async () => {
    const { wrapper, store } = mountPanel();
    await flushPromises();
    await wrapper.get('[data-testid="generate-video-btn"]').trigger("click");
    expect(store.generateVideoFromDraft).toHaveBeenCalledWith("SH1");
  });

  it("saves current prompt and references before generating video", async () => {
    const { wrapper, store } = mountPanel();
    await flushPromises();
    const updateSpy = vi.spyOn(store, "updateRenderDraft");
    const textarea = wrapper.get<HTMLTextAreaElement>('[data-testid="draft-prompt"]');

    await textarea.setValue("视频生成前编辑过的提示词");
    updateSpy.mockClear();
    await wrapper.get('[data-testid="generate-video-btn"]').trigger("click");

    expect(updateSpy).toHaveBeenCalledWith("SH1", {
      prompt: "视频生成前编辑过的提示词",
      references: expect.arrayContaining([
        expect.objectContaining({ id: "scene-1", name: "长安殿" }),
      ]),
    });
    expect(store.generateVideoFromDraft).toHaveBeenCalledWith("SH1");
  });

  it("shows Video Preview when current version has video", async () => {
    const { wrapper } = mountPanel({
      currentVersion: {
        id: "VID1",
        shot_id: "SH1",
        version_no: 1,
        status: "succeeded",
        prompt_snapshot: null,
        params_snapshot: { duration: 5, resolution: "720p", model_type: "fast" },
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
    await flushPromises();
    expect(wrapper.text()).toContain("Video Preview");
    expect(wrapper.find("video").exists()).toBe(true);
  });

  it("history modal lists video versions with playable status", async () => {
    const { wrapper } = mountPanelWithVideoHistory();
    await flushPromises();
    await wrapper.get('[data-testid="history-btn"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("版本 v2");
    expect(wrapper.text()).toContain("已完成");
  });

  it("hides the retry banner when a playable current video already exists", async () => {
    const { wrapper } = mountPanel({
      currentVersion: {
        id: "VID3",
        shot_id: "SH1",
        version_no: 3,
        status: "succeeded",
        prompt_snapshot: null,
        params_snapshot: { duration: 5, resolution: "720p", model_type: "fast" },
        video_url: "https://example.com/out.mp4",
        last_frame_url: "https://example.com/out.png",
        provider_task_id: "cgt-3",
        error_code: "volcano_error",
        error_msg: "InputImageSensitiveContentDetected.PrivacyInformation",
        created_at: "2026-04-23T12:00:00Z",
        finished_at: "2026-04-23T12:01:00Z",
        is_current: true
      }
    });
    await flushPromises();
    expect(wrapper.text()).not.toContain("最近一次生成失败");
    expect(wrapper.find("video").exists()).toBe(true);
  });

  it("does not show the retry banner even when the latest video version failed", async () => {
    const { wrapper } = mountPanelWithFailedVersion();
    await flushPromises();
    expect(wrapper.text()).not.toContain("最近一次生成失败");
    expect(wrapper.text()).not.toContain("MissingParameter");
  });

  it("closes the reference picker after adding a candidate", async () => {
    const { pinia, store } = setupStore();
    vi.spyOn(store, "referenceCandidatesFor").mockReturnValue([
      {
        id: "history-1",
        kind: "history",
        source_id: "R2",
        name: "视频尾帧 v1",
        alias: "视频尾帧 v1",
        mention_key: "history:R2:last_frame",
        image_url: "https://example.com/history.png",
        origin: "history",
        reason: "当前项目已生成视频尾帧",
      },
    ]);
    const wrapper = mount(GenerationPanel, { global: { plugins: [pinia] } });
    await flushPromises();

    await wrapper.get(".add-reference").trigger("click");
    expect(wrapper.text()).toContain("添加参考图");

    await wrapper.get(".candidate-card").trigger("click");
    await flushPromises();

    expect(wrapper.text()).not.toContain("添加参考图");
    expect(wrapper.text()).toContain("视频尾帧 v1");
    expect(wrapper.text()).toContain("2/6 张");
  });

  it("does not overwrite the whole prompt when @ is typed while all text is selected", async () => {
    const { wrapper } = mountPanel();
    await flushPromises();

    const textarea = wrapper.get<HTMLTextAreaElement>('[data-testid="draft-prompt"]');
    textarea.element.setSelectionRange(0, textarea.element.value.length);
    await textarea.setValue("@");
    await flushPromises();

    expect(textarea.element.value).toBe("原样提示词@");
    expect(wrapper.find('[data-testid="reference-mention-menu"]').exists()).toBe(true);

    textarea.element.setSelectionRange(0, "原样提示词".length);
    await wrapper.get(".mention-option").trigger("mousedown");
    await flushPromises();

    expect(textarea.element.value).toBe("原样提示词@长安殿 ");
  });

  it("replaces only the trailing @ when the prompt already starts with a reference", async () => {
    const { wrapper } = mountPanel();
    await flushPromises();

    const textarea = wrapper.get<HTMLTextAreaElement>('[data-testid="draft-prompt"]');
    await textarea.setValue("@图1作为核心场景基础@");
    textarea.element.setSelectionRange(textarea.element.value.length, textarea.element.value.length);
    await flushPromises();

    await wrapper.get(".mention-option").trigger("mousedown");
    await flushPromises();

    expect(textarea.element.value).toBe("@图1作为核心场景基础@长安殿 ");
  });

  it("does not open mention options for an old reference far before the cursor", async () => {
    const { wrapper } = mountPanel();
    await flushPromises();

    const textarea = wrapper.get<HTMLTextAreaElement>('[data-testid="draft-prompt"]');
    await textarea.setValue("@图1作为核心场景基础，8s，厚重乌云覆盖整座皇城上空，固定机位远景拍摄，画面无崩坏");
    textarea.element.setSelectionRange(textarea.element.value.length, textarea.element.value.length);
    await textarea.trigger("focus");
    await flushPromises();

    expect(wrapper.find('[data-testid="reference-mention-menu"]').exists()).toBe(false);
  });

  it("opens mention options when @ is typed in the middle of the prompt", async () => {
    const { wrapper } = mountPanel();
    await flushPromises();

    const textarea = wrapper.get<HTMLTextAreaElement>('[data-testid="draft-prompt"]');
    textarea.element.value = "前半段@，后半段";
    textarea.element.setSelectionRange("前半段@".length, "前半段@".length);
    await textarea.trigger("input");
    await flushPromises();

    expect(wrapper.find('[data-testid="reference-mention-menu"]').exists()).toBe(true);

    await wrapper.get(".mention-option").trigger("mousedown");
    await flushPromises();

    expect(textarea.element.value).toBe("前半段@长安殿 ，后半段");
  });

  it("disables manual reference submit until name and asset url are filled", async () => {
    const wrapper = mount(ReferencePickerModal, {
      props: {
        open: true,
        candidates: [],
        selected: [],
        maxCount: 6,
      },
    });

    const submit = () => wrapper.get<HTMLButtonElement>(".manual-form button");
    expect(submit().attributes("disabled")).toBeDefined();

    await wrapper.get('input[placeholder="名称"]').setValue("手动图");
    expect(submit().attributes("disabled")).toBeDefined();

    await wrapper
      .get('input[placeholder="projects/{project_id}/... 或 OBS 项目 URL"]')
      .setValue("projects/P1/manual/ref.png");
    expect(submit().attributes("disabled")).toBeUndefined();
  });
});
