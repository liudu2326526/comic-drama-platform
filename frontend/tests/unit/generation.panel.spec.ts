import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GenerationPanel from "@/components/generation/GenerationPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

describe("GenerationPanel", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("stage not renderable 时, 展示引导文案", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "P1",
      name: "Demo",
      stage: "角色已锁定",
      stage_raw: "characters_locked",
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
      generationProgress: "",
      generationNotes: { input: "", suggestion: "" },
      generationQueue: [],
      exportConfig: [],
      exportDuration: "",
      exportTasks: []
    } as never;

    const wrapper = mount(GenerationPanel, { global: { plugins: [pinia] } });
    expect(wrapper.text()).toContain("资产锁定后可开始镜头渲染");
  });

  it("先生成草稿再确认生成", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    const draft = {
      shot_id: "SH1",
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img/scene.png", reason: "命中文案" }]
    };
    vi.spyOn(store, "fetchRenderDraft").mockResolvedValue(draft as never);
    vi.spyOn(store, "renderDraftFor").mockReturnValue(draft as never);
    vi.spyOn(store, "confirmRenderShot").mockResolvedValue("RJ1");
    vi.spyOn(store, "fetchRenderVersions").mockResolvedValue([]);

    store.current = {
      id: "P1",
      name: "Demo",
      stage: "场景已匹配",
      stage_raw: "scenes_locked",
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
      exportTasks: []
    } as never;
    store.selectedShotId = "SH1";

    const wrapper = mount(GenerationPanel, { global: { plugins: [pinia] } });
    await flushPromises();

    await wrapper.get('[data-testid="generate-draft-btn"]').trigger("click");
    await flushPromises();

    expect((wrapper.get('[data-testid="draft-prompt"]').element as HTMLTextAreaElement).value).toContain("图片1中的宫门");
    expect(wrapper.text()).toContain("长安殿");

    await wrapper.get('[data-testid="confirm-render-btn"]').trigger("click");

    expect(store.confirmRenderShot).toHaveBeenCalledWith("SH1", {
      prompt: "图片1中的宫门，图片2中的主角。",
      references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img/scene.png" }]
    });
  });
});
