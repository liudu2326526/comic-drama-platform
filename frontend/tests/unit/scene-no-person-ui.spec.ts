import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it } from "vitest";
import SceneAssetsPanel from "@/components/scene/SceneAssetsPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

describe("scene no-person UI", () => {
  it("labels generated scene image as no-person reference", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "p1",
      stage_raw: "characters_locked",
      scenePromptProfile: { draft: null, applied: null, status: "empty" },
      sceneStyleReference: { imageUrl: null, prompt: null, status: "empty", error: null },
      characters: [],
      scenes: [
        {
          id: "s1",
          name: "朱雀门",
          theme: "palace",
          summary: "雨夜宫门",
          description: "无人宫门",
          meta: [],
          locked: false,
          template_id: null,
          reference_image_url: "scene.png",
          usage: ""
        }
      ],
      storyboards: []
    } as never;
    store.selectedSceneId = "s1";

    const wrapper = mount(SceneAssetsPanel, { global: { plugins: [pinia], stubs: ["StageRollbackModal"] } });

    expect(wrapper.text()).toContain("无人场景参考图");
  });
});
