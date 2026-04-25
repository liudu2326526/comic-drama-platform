import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it } from "vitest";
import CharacterAssetsPanel from "@/components/character/CharacterAssetsPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

describe("character dual image UI", () => {
  it("shows full body and headshot labels when selected character has both images", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "p1",
      stage_raw: "storyboard_ready",
      characterPromptProfile: { draft: null, applied: null, status: "empty" },
      characterStyleReference: { imageUrl: null, prompt: null, status: "empty", error: null },
      characters: [
        {
          id: "c1",
          name: "秦昭",
          role_type: "supporting",
          role: "配角",
          is_protagonist: false,
          locked: false,
          summary: "少年天子",
          description: "黑金冕服",
          meta: [],
          reference_image_url: "full.png",
          full_body_image_url: "full.png",
          headshot_image_url: "head.png"
        }
      ],
      scenes: [],
      storyboards: []
    } as never;
    store.selectedCharacterId = "c1";

    const wrapper = mount(CharacterAssetsPanel, { global: { plugins: [pinia], stubs: ["StageRollbackModal"] } });

    expect(wrapper.text()).toContain("全身参考图");
    expect(wrapper.text()).toContain("头像参考图");
  });
});
