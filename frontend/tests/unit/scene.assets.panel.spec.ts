import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it } from "vitest";
import SceneAssetsPanel from "@/components/scene/SceneAssetsPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

describe("SceneAssetsPanel", () => {
  it("M3b 仍保留绑定镜头入口，并标明它是进入 scenes_locked 的过渡步骤", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "P1",
      name: "Demo",
      stage: "角色已锁定",
      stage_raw: "characters_locked",
      storyboards: [{ id: "SH1", idx: 1, title: "开场", description: "", detail: "", duration_sec: 3, tags: [], status: "pending", scene_id: null, current_render_id: null, created_at: "", updated_at: "" }],
      scenes: [{ id: "SC1", name: "长安殿", summary: "宫门", description: "宫门", reference_image_url: "https://img", locked: true, theme: "palace", meta: [], usage: "场景复用 1 镜头" }],
      characters: [],
      genre: null,
      ratio: "9:16",
      suggestedShots: "",
      story: "",
      summary: "",
      parsedStats: [],
      setupParams: [],
      projectOverview: "",
      generationProgress: "",
      generationNotes: { input: "", suggestion: "" },
      generationQueue: [],
      exportConfig: [],
      exportDuration: "",
      exportTasks: []
    } as never;

    const wrapper = mount(SceneAssetsPanel, { global: { plugins: [pinia] } });
    expect(wrapper.text()).toContain("绑定镜头");
    expect(wrapper.text()).toContain("进入渲染阶段前仍需先完成镜头绑定");
  });
});
