import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/projects", () => ({
  projectsApi: {
    get: vi.fn(),
    getJobs: vi.fn()
  }
}));

vi.mock("@/api/shots", () => ({
  shotsApi: {
    generateRenderDraft: vi.fn(),
    getRenderDraft: vi.fn(),
    render: vi.fn(),
    generateVideo: vi.fn(),
    listRenders: vi.fn(),
    selectRender: vi.fn(),
    listVideos: vi.fn(),
    selectVideo: vi.fn(),
    lock: vi.fn()
  }
}));

import { projectsApi } from "@/api/projects";
import { shotsApi } from "@/api/shots";
import { useWorkbenchStore } from "@/store/workbench";

const mkProject = (overrides: Partial<import("@/types").ProjectData> = {}) => ({
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
    current_video_render_id: "V1",
    current_video_url: "https://example.com/v1.mp4",
    current_last_frame_url: "https://example.com/v1.png",
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

describe("workbench M3b render actions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("fetchRenderDraft(): 读取并缓存已保存草稿", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "getRenderDraft").mockResolvedValue({
      shot_id: "SH1",
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{ id: "scene-1", kind: "scene", source_id: "scene01", name: "长安殿", image_url: "https://img", reason: "命中文案" }]
    } as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    const draft = await store.fetchRenderDraft("SH1");

    expect(draft.prompt).toContain("图片1");
    expect(store.renderDraftFor("SH1")?.references).toHaveLength(1);
  });

  it("generateRenderDraft(): 写入 activeDraftJobId 与 activeDraftShotId", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "generateRenderDraft").mockResolvedValue({ job_id: "DJ1", sub_job_ids: [] } as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.generateRenderDraft("SH1");

    expect(jobId).toBe("DJ1");
    expect(store.activeDraftJobId).toBe("DJ1");
    expect(store.activeDraftShotId).toBe("SH1");
  });

  it("generateRenderDraft(): 允许不同镜头并发草稿任务", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(
      mkProject({
        storyboards: [
          {
            id: "SH1",
            idx: 1,
            title: "镜头一",
            description: "开场",
            detail: "",
            duration_sec: 3,
            tags: [],
            scene_id: "SC1",
            status: "pending",
            current_render_id: null,
            current_video_render_id: null,
            current_video_url: null,
            current_last_frame_url: null,
            current_video_version_no: null,
            current_video_params_snapshot: null,
            created_at: "2026-04-22T00:00:00Z",
            updated_at: "2026-04-22T00:00:00Z"
          },
          {
            id: "SH2",
            idx: 2,
            title: "镜头二",
            description: "转场",
            detail: "",
            duration_sec: 3,
            tags: [],
            scene_id: "SC2",
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
      }) as never
    );
    vi.spyOn(shotsApi, "generateRenderDraft")
      .mockResolvedValueOnce({ job_id: "DJ1", sub_job_ids: [] } as never)
      .mockResolvedValueOnce({ job_id: "DJ2", sub_job_ids: [] } as never);

    const store = useWorkbenchStore();
    await store.load("P1");

    await store.generateRenderDraft("SH1");
    await store.generateRenderDraft("SH2");

    expect(store.draftJobIdFor("SH1")).toBe("DJ1");
    expect(store.draftJobIdFor("SH2")).toBe("DJ2");
  });

  it("generateRenderDraft(): 同镜头重复提交仍然阻止", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "generateRenderDraft").mockResolvedValue({ job_id: "DJ1", sub_job_ids: [] } as never);

    const store = useWorkbenchStore();
    await store.load("P1");

    await store.generateRenderDraft("SH1");

    await expect(store.generateRenderDraft("SH1")).rejects.toThrow("该镜头已有草稿生成任务进行中");
  });

  it("generateVideoFromDraft(): 写入 activeRenderJobId 与 activeRenderShotId", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "generateVideo").mockResolvedValue({ job_id: "VJ1", sub_job_ids: [] } as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    store.updateRenderDraft("SH1", {
      shot_id: "SH1",
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{
        id: "scene-1",
        kind: "scene",
        source_id: "SC1",
        name: "长安殿",
        image_url: "https://img",
        reason: "命中文案"
      }]
    });
    store.setVideoDraftOptions("SH1", { duration: null, resolution: "480p", modelType: "fast" });
    const jobId = await store.generateVideoFromDraft("SH1");

    expect(jobId).toBe("VJ1");
    expect(store.activeRenderJobId).toBe("VJ1");
    expect(store.activeRenderShotId).toBe("SH1");
    expect(shotsApi.generateVideo).toHaveBeenCalledWith("P1", "SH1", {
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{
        id: "scene-1",
        kind: "scene",
        source_id: "SC1",
        name: "长安殿",
        image_url: "https://img"
      }],
      resolution: "480p",
      model_type: "fast"
    });
  });

  it("fetchVideoVersions(): 缓存版本历史", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "listVideos").mockResolvedValue([
      {
        id: "V1",
        shot_id: "SH1",
        version_no: 1,
        status: "succeeded",
        prompt_snapshot: {},
        params_snapshot: { duration: 5, resolution: "720p", model_type: "fast" },
        video_url: "https://video",
        last_frame_url: "https://img",
        provider_task_id: null,
        error_code: null,
        error_msg: null,
        created_at: "2026-04-22T00:00:00Z",
        finished_at: null,
        is_current: true
      }
    ] as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    const rows = await store.fetchVideoVersions("SH1");

    expect(rows).toHaveLength(1);
    expect(store.videoVersionsFor("SH1")[0].id).toBe("V1");
  });

  it("findAndTrackActiveJobs(): 在 rendering 阶段接管 in-flight render_shot_video job", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(
      mkProject({
        stage: "镜头生成中",
        stage_raw: "rendering"
      }) as never
    );
    vi.spyOn(projectsApi, "getJobs").mockResolvedValue([
      {
        id: "VJ2",
        kind: "render_shot_video",
        status: "running",
        progress: 45,
        total: 100,
        done: 45,
        payload: { video_render_id: "V2", shot_id: "SH1" },
        result: null,
        error_msg: null,
        target_id: "SH1",
        created_at: "2026-04-22T00:00:00Z",
        finished_at: null
      }
    ] as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    await store.findAndTrackActiveJobs();

    expect(store.activeRenderJobId).toBe("VJ2");
    expect(store.activeRenderShotId).toBe("SH1");
  });

  it("findAndTrackActiveJobs(): 在 scenes_locked 阶段接管多个 in-flight gen_shot_draft job", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(projectsApi, "getJobs").mockResolvedValue([
      {
        id: "DJ2",
        kind: "gen_shot_draft",
        status: "running",
        progress: 30,
        total: 4,
        done: 1,
        payload: { shot_id: "SH1" },
        result: null,
        error_msg: null,
        target_id: "SH1",
        created_at: "2026-04-22T00:00:00Z",
        finished_at: null
      },
      {
        id: "DJ3",
        kind: "gen_shot_draft",
        status: "queued",
        progress: 0,
        total: 4,
        done: 0,
        payload: { shot_id: "SH2" },
        result: null,
        error_msg: null,
        target_id: "SH2",
        created_at: "2026-04-22T00:01:00Z",
        finished_at: null
      }
    ] as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    await store.findAndTrackActiveJobs();

    expect(store.activeDraftJobId).toBe("DJ2");
    expect(store.activeDraftShotId).toBe("SH1");
    expect(store.draftJobIdFor("SH1")).toBe("DJ2");
    expect(store.draftJobIdFor("SH2")).toBe("DJ3");
  });
});
