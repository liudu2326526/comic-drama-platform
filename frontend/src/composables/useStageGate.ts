/* frontend/src/composables/useStageGate.ts */
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import type { ProjectStageRaw } from "@/types/api";

export interface StageGateFlags {
  canEditStoryboards: boolean;
  canGenerateCharacters: boolean;
  canGenerateScenes: boolean;
  canEditCharacters: boolean;
  canEditScenes: boolean;
  canBindScene: boolean;
  canRegisterCharacterAsset: boolean;
  canConfirmCharacters: boolean;
  canConfirmScenes: boolean;
  canRender: boolean;
  canExport: boolean;
  canLockShot: boolean;
  canRollback: boolean;
}

export function gateFlags(raw: ProjectStageRaw | null | undefined): StageGateFlags {
  const isStoryboardReady = raw === "storyboard_ready";
  const isCharactersLocked = raw === "characters_locked";
  const canRegisterCharacterAsset =
    raw === "storyboard_ready" ||
    raw === "characters_locked" ||
    raw === "scenes_locked" ||
    raw === "rendering" ||
    raw === "ready_for_export" ||
    raw === "exported";
  return {
    canEditStoryboards: raw === "draft" || isStoryboardReady,
    canGenerateCharacters: isStoryboardReady,
    canGenerateScenes: isCharactersLocked,
    canEditCharacters: isStoryboardReady,
    canEditScenes: isCharactersLocked,
    canBindScene: isCharactersLocked,
    canRegisterCharacterAsset,
    canConfirmCharacters: isStoryboardReady,
    canConfirmScenes: isCharactersLocked,
    canRender: raw === "scenes_locked" || raw === "rendering" || raw === "ready_for_export",
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
