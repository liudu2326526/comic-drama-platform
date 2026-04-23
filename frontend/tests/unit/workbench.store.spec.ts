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
  it("reload 默认静默刷新, 请求进行中不切回 loading skeleton", async () => {
    let resolveGet!: (value: typeof FAKE_PROJECT) => void;
    (projectsApi.get as ReturnType<typeof vi.fn>).mockImplementation(
      () =>
        new Promise<typeof FAKE_PROJECT>((resolve) => {
          resolveGet = resolve;
        })
    );

    const store = useWorkbenchStore();
    store.current = FAKE_PROJECT as never;
    store.loading = false;

    const pending = store.reload();
    expect(store.loading).toBe(false);

    resolveGet(FAKE_PROJECT);
    await pending;
    expect(store.loading).toBe(false);
  });

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
