import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import { projectsApi } from "@/api/projects";
import { promptProfilesApi } from "@/api/promptProfiles";
import { scenesApi } from "@/api/scenes";

const emptyProfile = {
  draft: null,
  applied: null,
  status: "empty" as const
};

const mkProject = (overrides: Partial<import("@/types").ProjectData> = {}) => ({
  id: "P1",
  name: "Demo",
  stage: "角色已锁定" as const,
  stage_raw: "characters_locked" as const,
  genre: null,
  ratio: "9:16",
  suggestedShots: "",
  story: "",
  summary: "",
  parsedStats: [],
  setupParams: [],
  projectOverview: "",
  storyboards: [],
  characters: [],
  scenes: [],
  characterPromptProfile: emptyProfile,
  scenePromptProfile: emptyProfile,
  generationProgress: "",
  generationNotes: { input: "", suggestion: "" },
  generationQueue: [],
  exportConfig: [],
  exportDuration: "",
  exportTasks: [],
  ...overrides
});

describe("workbench prompt profile actions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("savePromptProfileDraft: updates current project prompt profile state", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    vi.spyOn(promptProfilesApi, "updateDraft").mockResolvedValue({
      draft: { prompt: "冷青灰宫廷电影感", source: "manual" },
      applied: null,
      status: "draft_only"
    });

    const store = useWorkbenchStore();
    await store.load("P1");
    const state = await store.savePromptProfileDraft("scene", "冷青灰宫廷电影感");

    expect(state.status).toBe("draft_only");
    expect(store.current?.scenePromptProfile.draft?.prompt).toBe("冷青灰宫廷电影感");
  });

  it("restoreAppliedPromptProfileDraft: copies applied prompt back into draft lane", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(
      mkProject({
        scenePromptProfile: {
          draft: { prompt: "旧草稿", source: "manual" },
          applied: { prompt: "稳定已应用版本", source: "ai" },
          status: "dirty"
        }
      }) as never
    );
    const updateSpy = vi.spyOn(promptProfilesApi, "updateDraft").mockResolvedValue({
      draft: { prompt: "稳定已应用版本", source: "manual" },
      applied: { prompt: "稳定已应用版本", source: "ai" },
      status: "applied"
    });

    const store = useWorkbenchStore();
    await store.load("P1");
    await store.restoreAppliedPromptProfileDraft("scene");

    expect(updateSpy).toHaveBeenCalledWith("P1", "scene", "稳定已应用版本");
    expect(store.current?.scenePromptProfile.status).toBe("applied");
  });

  it("confirmPromptProfileAndGenerate: character lane stores downstream generate job id", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(
      mkProject({
        stage: "分镜已生成",
        stage_raw: "storyboard_ready",
        characterPromptProfile: {
          draft: { prompt: "统一角色视觉锚点", source: "manual" },
          applied: null,
          status: "draft_only"
        }
      }) as never
    );
    vi.spyOn(promptProfilesApi, "confirm").mockResolvedValue({ job_id: "J1", sub_job_ids: [] });

    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.confirmPromptProfileAndGenerate("character");

    expect(jobId).toBe("J1");
    expect(store.activeGenerateCharactersJobId).toBe("J1");
    expect(store.current?.characterPromptProfile.status).toBe("applied");
  });

  it("skipPromptProfileAndGenerate: scene lane reuses existing generate action", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(mkProject() as never);
    const generateSpy = vi.spyOn(scenesApi, "generate").mockResolvedValue({
      job_id: "SJ1",
      sub_job_ids: []
    });

    const store = useWorkbenchStore();
    await store.load("P1");
    const jobId = await store.skipPromptProfileAndGenerate("scene");

    expect(generateSpy).toHaveBeenCalledWith("P1", {});
    expect(jobId).toBe("SJ1");
    expect(store.activeGenerateScenesJobId).toBe("SJ1");
  });

  it("findAndTrackActiveJobs: resumes prompt profile job and batch regenerate job kinds", async () => {
    vi.spyOn(projectsApi, "get").mockResolvedValue(
      mkProject({
        stage: "分镜已生成",
        stage_raw: "storyboard_ready"
      }) as never
    );
    vi.spyOn(projectsApi, "getJobs").mockResolvedValue([
      {
        id: "PJ1",
        kind: "gen_character_prompt_profile",
        status: "running",
        progress: 35,
        total: null,
        done: 0,
        payload: null,
        result: null,
        error_msg: null,
        created_at: "2026-04-23T00:00:00Z",
        finished_at: null
      },
      {
        id: "BJ1",
        kind: "regen_character_assets_batch",
        status: "queued",
        progress: 0,
        total: null,
        done: 0,
        payload: null,
        result: null,
        error_msg: null,
        created_at: "2026-04-23T00:00:00Z",
        finished_at: null
      }
    ] as never);

    const store = useWorkbenchStore();
    await store.load("P1");
    await store.findAndTrackActiveJobs();

    expect(store.activeCharacterPromptProfileJobId).toBe("PJ1");
    expect(store.activeGenerateCharactersJobId).toBe("BJ1");
  });
});
