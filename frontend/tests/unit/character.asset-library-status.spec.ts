import { describe, expect, it } from "vitest";

import type { CharacterAsset } from "@/types";
import {
  getCharacterAssetLibraryAction,
  getCharacterAssetLibraryBadge,
  getCharacterAssetLibraryState
} from "@/utils/characterAssetLibrary";

function makeCharacter(meta: string[]): CharacterAsset {
  return {
    id: "C1",
    name: "萧景珩",
    role: "配角",
    is_protagonist: false,
    locked: false,
    summary: "",
    description: "",
    meta,
    reference_image_url: null
  };
}

describe("character asset library status", () => {
  it("treats 人像库:Pending as pending state", () => {
    const character = makeCharacter(["人像库:Pending"]);

    expect(getCharacterAssetLibraryState(character)).toBe("pending");
    expect(getCharacterAssetLibraryBadge(character)).toBe("入库中");
    expect(getCharacterAssetLibraryAction(character)).toEqual({
      label: "入库中",
      disabled: true
    });
  });

  it("treats 人像库:Active as active state", () => {
    const character = makeCharacter(["人像库:Active"]);

    expect(getCharacterAssetLibraryState(character)).toBe("active");
    expect(getCharacterAssetLibraryBadge(character)).toBe("已入人像库");
    expect(getCharacterAssetLibraryAction(character)).toEqual({
      label: "已入人像库",
      disabled: true
    });
  });

  it("keeps register action enabled when no asset library tag exists", () => {
    const character = makeCharacter(["核心角色"]);

    expect(getCharacterAssetLibraryState(character)).toBe("idle");
    expect(getCharacterAssetLibraryBadge(character)).toBeNull();
    expect(getCharacterAssetLibraryAction(character)).toEqual({
      label: "入人像库",
      disabled: false
    });
  });
});
