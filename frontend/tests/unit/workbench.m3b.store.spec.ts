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
    renderDraft: vi.fn(),
    render: vi.fn(),
    listRenders: vi.fn(),
    selectRender: vi.fn(),
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

  it("fetchRenderDraft(): 缓存后端建议 prompt 与 references", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "renderDraft").mockResolvedValue({
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

  it("confirmRenderShot(): 写入 activeRenderJobId 与 activeRenderShotId", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "render").mockResolvedValue({ job_id: "RJ1", sub_job_ids: [] } as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.confirmRenderShot("SH1", {
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img" }]
    });

    expect(jobId).toBe("RJ1");
    expect(store.activeRenderJobId).toBe("RJ1");
    expect(store.activeRenderShotId).toBe("SH1");
  });

  it("fetchRenderVersions(): 缓存版本历史", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(shotsApi, "listRenders").mockResolvedValue([
      {
        id: "R1",
        shot_id: "SH1",
        version_no: 1,
        status: "succeeded",
        prompt_snapshot: {},
        image_url: "https://img",
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
    const rows = await store.fetchRenderVersions("SH1");

    expect(rows).toHaveLength(1);
    expect(store.renderVersionsFor("SH1")[0].id).toBe("R1");
  });

  it("findAndTrackActiveJobs(): 在 rendering 阶段接管 in-flight render_shot job", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(
      mkProject({
        stage: "镜头生成中",
        stage_raw: "rendering"
      }) as never
    );
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
      }
    ] as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    await store.findAndTrackActiveJobs();

    expect(store.activeRenderJobId).toBe("RJ2");
    expect(store.activeRenderShotId).toBe("SH1");
  });
});
