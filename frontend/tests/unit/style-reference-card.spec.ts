import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StyleReferenceCard from "@/components/common/StyleReferenceCard.vue";

describe("StyleReferenceCard", () => {
  it("renders empty character reference state", () => {
    const wrapper = mount(StyleReferenceCard, {
      props: {
        kind: "character",
        state: { imageUrl: null, prompt: null, status: "empty", error: null },
        disabled: false,
        running: false
      }
    });

    expect(wrapper.text()).toContain("统一角色形象参考图");
    expect(wrapper.text()).toContain("生成参考图");
  });

  it("emits generate when action is clicked", async () => {
    const wrapper = mount(StyleReferenceCard, {
      props: {
        kind: "scene",
        state: { imageUrl: null, prompt: null, status: "empty", error: null },
        disabled: false,
        running: false
      }
    });

    await wrapper.get("button").trigger("click");

    expect(wrapper.emitted("generate")).toHaveLength(1);
  });
});
