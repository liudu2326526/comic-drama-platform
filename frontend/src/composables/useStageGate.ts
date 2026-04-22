/* frontend/src/composables/useStageGate.ts */
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import type { ProjectStageRaw } from "@/types/api";

export interface StageGateFlags {
  canEditStoryboards: boolean;
  canGenerateCharacters: boolean;
  canGenerateScenes: boolean;
  canRender: boolean;
  canExport: boolean;
  canLockShot: boolean;
  canRollback: boolean;
}

export function gateFlags(raw: ProjectStageRaw | null | undefined): StageGateFlags {
  return {
    canEditStoryboards: raw === "draft" || raw === "storyboard_ready",
    canGenerateCharacters: raw === "storyboard_ready",
    canGenerateScenes: raw === "characters_locked",
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
