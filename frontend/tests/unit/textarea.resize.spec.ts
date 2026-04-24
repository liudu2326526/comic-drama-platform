import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "../..");

function read(relativePath: string) {
  return readFileSync(resolve(root, relativePath), "utf-8");
}

describe("textarea resize styling", () => {
  it("disables manual textarea resizing across the app", () => {
    expect(read("src/styles/global.css")).toContain("resize: none;");
    expect(read("src/components/generation/GenerationPanel.vue")).not.toContain("resize: vertical;");
    expect(read("src/components/common/PromptProfileCard.vue")).not.toContain("resize: vertical;");
  });
});
