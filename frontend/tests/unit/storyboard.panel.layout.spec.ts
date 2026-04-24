import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it } from "vitest";
import StoryboardPanel from "@/components/storyboard/StoryboardPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

const makeShot = (idx: number) => ({
  id: `SH${idx}`,
  idx,
  title: `镜头 ${idx}`,
  description: "雨夜宫门，人物在压抑氛围中行动。",
  detail: "8秒，9:16竖屏。0-2s：全景；2-5s：中景；5-8s：特写。",
  duration_sec: 8,
  tags: ["雨夜", "宫变"],
  scene_id: null,
  status: "pending" as const,
  current_render_id: null,
  created_at: "2026-04-24T00:00:00Z",
  updated_at: "2026-04-24T00:00:00Z"
});

describe("StoryboardPanel layout", () => {
  it("uses a viewport-sized scroll region for cards and a sticky detail panel", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkbenchStore();
    store.current = {
      id: "P1",
      name: "Demo",
      stage: "分镜待确认",
      stage_raw: "storyboard_ready",
      storyboards: Array.from({ length: 8 }, (_, i) => makeShot(i + 1)),
      characters: [],
      scenes: [],
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
    store.selectedShotId = "SH4";

    const wrapper = mount(StoryboardPanel, { global: { plugins: [pinia] } });

    expect(wrapper.find(".storyboard-scroll").exists()).toBe(true);
    expect(wrapper.find(".storyboard-detail-shell").exists()).toBe(true);
    expect(wrapper.find(".storyboard-detail-body").text()).toContain("0-2s");
  });
});
