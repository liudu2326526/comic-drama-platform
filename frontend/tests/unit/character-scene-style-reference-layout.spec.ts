import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it, vi } from "vitest";
import CharacterAssetsPanel from "@/components/character/CharacterAssetsPanel.vue";
import SceneAssetsPanel from "@/components/scene/SceneAssetsPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

describe("style reference layout", () => {
  it("renders character style reference next to character profile", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "p1",
      stage_raw: "storyboard_ready",
      characterPromptProfile: { draft: null, applied: null, status: "empty" },
      characterStyleReference: { imageUrl: null, prompt: null, status: "empty", error: null },
      characters: [],
      scenes: [],
      storyboards: []
    } as never;
    vi.spyOn(store, "generateStyleReference").mockResolvedValue("job-style");

    const wrapper = mount(CharacterAssetsPanel, { global: { plugins: [pinia], stubs: ["StageRollbackModal"] } });

    expect(wrapper.text()).toContain("统一角色形象参考图");
  });

  it("renders scene style reference next to scene profile", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "p1",
      stage_raw: "characters_locked",
      scenePromptProfile: { draft: null, applied: null, status: "empty" },
      sceneStyleReference: { imageUrl: null, prompt: null, status: "empty", error: null },
      characters: [],
      scenes: [],
      storyboards: []
    } as never;
    vi.spyOn(store, "generateStyleReference").mockResolvedValue("job-style");

    const wrapper = mount(SceneAssetsPanel, { global: { plugins: [pinia], stubs: ["StageRollbackModal"] } });

    expect(wrapper.text()).toContain("统一场景视觉参考图");
  });
});
