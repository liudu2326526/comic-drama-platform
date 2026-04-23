import type { CharacterAsset } from "@/types";

export type CharacterAssetLibraryState = "idle" | "pending" | "active";

function getAssetStatusTag(character: CharacterAsset): string | null {
  const tag = character.meta.find((item) => item.startsWith("人像库:"));
  if (!tag) return null;
  return tag.slice("人像库:".length).trim() || null;
}

export function getCharacterAssetLibraryState(
  character: CharacterAsset
): CharacterAssetLibraryState {
  const status = getAssetStatusTag(character);
  if (status === "Pending") return "pending";
  if (status === "Active") return "active";
  return "idle";
}

export function getCharacterAssetLibraryBadge(character: CharacterAsset): string | null {
  const state = getCharacterAssetLibraryState(character);
  if (state === "pending") return "入库中";
  if (state === "active") return "已入人像库";
  return null;
}

export function getCharacterAssetLibraryAction(character: CharacterAsset): {
  label: string;
  disabled: boolean;
} {
  const state = getCharacterAssetLibraryState(character);
  if (state === "pending") {
    return { label: "入库中", disabled: true };
  }
  if (state === "active") {
    return { label: "已入人像库", disabled: true };
  }
  return { label: "入人像库", disabled: false };
}
