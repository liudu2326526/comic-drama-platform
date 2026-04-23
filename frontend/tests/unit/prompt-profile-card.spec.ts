import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import PromptProfileCard from "@/components/common/PromptProfileCard.vue";

describe("PromptProfileCard", () => {
  it("empty: shows skip action for first-time generation", () => {
    const wrapper = mount(PromptProfileCard, {
      props: {
        title: "角色统一视觉设定",
        description: "用于统一角色参考图风格。",
        profile: { draft: null, applied: null, status: "empty" },
        editable: true
      }
    });

    expect(wrapper.text()).toContain("跳过并直接生成");
    expect(wrapper.text()).toContain("AI 生成建议");
  });

  it("draft_only: shows confirm action for new config", () => {
    const wrapper = mount(PromptProfileCard, {
      props: {
        title: "角色统一视觉设定",
        description: "用于统一角色参考图风格。",
        profile: {
          draft: { prompt: "冷青灰宫廷电影感", source: "manual" },
          applied: null,
          status: "draft_only"
        },
        editable: true
      }
    });

    expect(wrapper.text()).toContain("确认新配置并生成");
    expect(wrapper.text()).toContain("清空草稿");
  });

  it("applied: shows rerun action for current profile", () => {
    const wrapper = mount(PromptProfileCard, {
      props: {
        title: "场景统一视觉设定",
        description: "用于统一场景母版风格。",
        profile: {
          draft: { prompt: "稳定版本", source: "ai" },
          applied: { prompt: "稳定版本", source: "ai" },
          status: "applied"
        },
        editable: true
      }
    });

    expect(wrapper.text()).toContain("按当前配置重新生成");
  });

  it("dirty: shows restore action for applied version", async () => {
    const wrapper = mount(PromptProfileCard, {
      props: {
        title: "场景统一视觉设定",
        description: "用于统一场景母版风格。",
        profile: {
          draft: { prompt: "新草稿", source: "manual" },
          applied: { prompt: "旧已应用", source: "ai" },
          status: "dirty"
        },
        editable: true
      }
    });

    expect(wrapper.text()).toContain("恢复到已应用版本");
    await wrapper.get('[data-testid="prompt-profile-restore"]').trigger("click");
    expect(wrapper.emitted("restore")).toHaveLength(1);
  });
});
