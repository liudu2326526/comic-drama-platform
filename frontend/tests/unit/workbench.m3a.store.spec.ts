/* frontend/tests/unit/workbench.m3a.store.spec.ts */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import { projectsApi } from "@/api/projects";
import { charactersApi } from "@/api/characters";
import { scenesApi } from "@/api/scenes";
import { storyboardsApi } from "@/api/storyboards";

const mkProject = (overrides: Partial<import("@/types").ProjectData> = {}) => ({
  id: "P1",
  name: "Demo",
  stage: "角色设定中" as const,
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

describe("workbench M3a actions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("generateCharacters: 写入 activeGenerateCharactersJobId 并返回 job_id", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as any);
    vi.spyOn(charactersApi, "generate").mockResolvedValue({
      job_id: "J1",
      sub_job_ids: ["s1", "s2"]
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.generateCharacters({ extra_hints: [] });
    expect(jobId).toBe("J1");
    expect(store.activeGenerateCharactersJobId).toBe("J1");
  });

  it("registerCharacterAsset(): 异步, 写入 activeRegisterCharacterAssetJobId 且不立即 reload", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      characters: [{
        id: "C1", name: "秦昭", role: "配角", is_protagonist: false,
        locked: false, summary: "", description: "", meta: [], reference_image_url: null
      }]
    }) as any);
    const lockSpy = vi.spyOn(charactersApi, "registerAsset").mockResolvedValue({
      job_id: "LJ1",
      sub_job_ids: []
    } as any);
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.registerCharacterAsset("C1");
    expect(lockSpy).toHaveBeenCalledWith("P1", "C1");
    expect(store.activeRegisterCharacterAssetJobId).toBe("LJ1");
    expect(store.activeRegisterCharacterAssetCharacterId).toBe("C1");
    // 只有初始 load, 没有 lock 后的 reload
    expect(projectsApi.get).toHaveBeenCalledTimes(1);
  });

  it("rendering 阶段刷新时也会找回入人像库任务", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "镜头生成中",
      stage_raw: "rendering",
      characters: [{
        id: "C1", name: "秦昭", role: "配角", is_protagonist: false,
        locked: false, summary: "", description: "", meta: [], reference_image_url: null
      }]
    }) as any);
    vi.spyOn(projectsApi, "getJobs").mockResolvedValue([
      {
        id: "LJ2",
        kind: "register_character_asset",
        status: "running",
        progress: 0,
        done: 2,
        total: 3,
        created_at: "2026-04-21T00:00:00Z",
        finished_at: null,
        payload: { character_id: "C1" },
        result: null,
        error_msg: null
      }
    ] as any);
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.findAndTrackActiveJobs();
    expect(store.activeRegisterCharacterAssetJobId).toBe("LJ2");
    expect(store.activeRegisterCharacterAssetCharacterId).toBe("C1");
  });

  it("confirmCharactersStage(): 完成后 reload", async () => {
    const getSpy = vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      characters: [{
        id: "C1", name: "秦昭", role: "配角", is_protagonist: false,
        locked: false, summary: "", description: "", meta: [], reference_image_url: null
      }]
    }) as any);
    const lockSpy = vi.spyOn(charactersApi, "confirmStage").mockResolvedValue({
      stage: "characters_locked",
      stage_raw: "characters_locked"
    } as any);
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.confirmCharactersStage();
    expect(lockSpy).toHaveBeenCalledWith("P1");
    expect(getSpy).toHaveBeenCalledTimes(2); // load + reload
    expect(store.activeRegisterCharacterAssetJobId).toBeNull();
  });

  it("regenerateCharacter: 单项 job 记在 regenJobs['character:<id>']", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      characters: [{
        id: "C1", name: "秦昭", role: "主角", is_protagonist: false,
        locked: false, summary: "", description: "", meta: [], reference_image_url: null
      }]
    }) as any);
    vi.spyOn(charactersApi, "regenerate").mockResolvedValue({
      job_id: "RJ1", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.regenerateCharacter("C1");
    expect(jobId).toBe("RJ1");
    expect(store.regenJobIdFor("character", "C1")).toBe("RJ1");
    expect(store.activeRegenJobEntries).toEqual([{ key: "character:C1", jobId: "RJ1" }]);
    store.markRegenByKeySucceeded("character:C1");
    expect(store.regenJobIdFor("character", "C1")).toBeNull();
  });

  it("regenerateCharacter: 同一项目已有角色重生成时拒绝并发", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      characters: [
        { id: "C1", name: "秦昭", role: "主角", is_protagonist: false, locked: false, summary: "", description: "", meta: [], reference_image_url: null },
        { id: "C2", name: "江离", role: "配角", is_protagonist: false, locked: false, summary: "", description: "", meta: [], reference_image_url: null }
      ]
    }) as any);
    vi.spyOn(charactersApi, "regenerate").mockResolvedValue({
      job_id: "RJ1", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.regenerateCharacter("C1");
    await expect(store.regenerateCharacter("C2")).rejects.toThrow("已有角色重生成任务进行中");
  });

  it("bindShotScene: POST + reload", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "场景设定中",
      stage_raw: "characters_locked"
    }) as any);
    const bindSpy = vi.spyOn(storyboardsApi, "bindScene").mockResolvedValue({
      shot_id: "SH1", scene_id: "SC1", scene_name: "长安殿"
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.bindShotScene("SH1", "SC1");
    expect(bindSpy).toHaveBeenCalledWith("P1", "SH1", { scene_id: "SC1" });
  });

  it("generateScenes: 写入 activeGenerateScenesJobId", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "场景设定中",
      stage_raw: "characters_locked"
    }) as any);
    vi.spyOn(scenesApi, "generate").mockResolvedValue({
      job_id: "J2", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.generateScenes({ template_whitelist: [] });
    expect(jobId).toBe("J2");
    expect(store.activeGenerateScenesJobId).toBe("J2");
  });

  it("regenerateScene: 同一项目已有场景重生成时拒绝并发", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "场景设定中",
      stage_raw: "characters_locked",
      scenes: [
        { id: "S1", name: "长安殿", theme: "palace", summary: "", usage: "", description: "", meta: [], locked: false, reference_image_url: null },
        { id: "S2", name: "御花园", theme: "palace", summary: "", usage: "", description: "", meta: [], locked: false, reference_image_url: null }
      ]
    }) as any);
    vi.spyOn(scenesApi, "regenerate").mockResolvedValue({
      job_id: "SRJ1", sub_job_ids: []
    });
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.regenerateScene("S1");
    await expect(store.regenerateScene("S2")).rejects.toThrow("已有场景重生成任务进行中");
  });

  it("confirmScenesStage(): 完成后 reload", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject({
      stage: "场景设定中",
      stage_raw: "characters_locked",
      scenes: [{
        id: "S1", name: "长安殿", theme: "palace", summary: "", usage: "",
        description: "", meta: [], locked: false, reference_image_url: null
      }]
    }) as any);
    const lockSpy = vi.spyOn(scenesApi, "confirmStage").mockResolvedValue({
      stage: "scenes_locked", stage_raw: "scenes_locked"
    } as any);
    const store = useWorkbenchStore();
    await store.load("P1");
    await store.confirmScenesStage();
    expect(lockSpy).toHaveBeenCalledWith("P1");
    expect(projectsApi.get).toHaveBeenCalledTimes(2);
  });
});
