/* frontend/src/composables/useStageGate.ts */
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import type { ProjectStageRaw } from "@/types/api";

export interface StageGateFlags {
  canEditStoryboards: boolean;
  canGenerateCharacters: boolean;
  canGenerateScenes: boolean;
  canEditCharacters: boolean; // M3a 新增:角色编辑窗口(严格对齐后端 assert_asset_editable("character") = storyboard_ready)
  canEditScenes: boolean; // M3a 新增:scenes 编辑窗口(= characters_locked)
  canBindScene: boolean; // M3a 新增:bind_scene 仅在 characters_locked 允许
  canLockCharacter: boolean; // M3a 新增:lock 接口后端要求 stage_raw ∈ {storyboard_ready}
  canLockScene: boolean; // M3a 新增:lock scene 要求 stage_raw ∈ {characters_locked}
  canRender: boolean;
  canExport: boolean;
  canLockShot: boolean;
  canRollback: boolean;
}

export function gateFlags(raw: ProjectStageRaw | null | undefined): StageGateFlags {
  const isStoryboardReady = raw === "storyboard_ready";
  const isCharactersLocked = raw === "characters_locked";
  return {
    canEditStoryboards: raw === "draft" || isStoryboardReady,
    canGenerateCharacters: isStoryboardReady,
    canGenerateScenes: isCharactersLocked,
    canEditCharacters: isStoryboardReady,
    canEditScenes: isCharactersLocked,
    canBindScene: isCharactersLocked,
    canLockCharacter: isStoryboardReady,
    canLockScene: isCharactersLocked,
    canRender: raw === "scenes_locked" || raw === "rendering",
    canExport: raw === "ready_for_export",
    canLockShot: raw === "rendering" || raw === "ready_for_export",
    canRollback: !!raw && raw !== "draft"
  };
}

export function useStageGate() {
  const { current } = storeToRefs(useWorkbenchStore());
  const flags = computed(() => gateFlags(current.value?.stage_raw ?? null));
  return { flags };
}
