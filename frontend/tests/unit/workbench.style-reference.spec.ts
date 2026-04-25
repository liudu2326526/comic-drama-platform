import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import { styleReferencesApi } from "@/api/styleReferences";

describe("workbench style references", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("starts character style reference job", async () => {
    vi.spyOn(styleReferencesApi, "generateStyleReference").mockResolvedValue({ job_id: "job-character", sub_job_ids: [] });
    const store = useWorkbenchStore();
    store.current = { id: "project-1", stage_raw: "storyboard_ready" } as never;

    await store.generateStyleReference("character");

    expect(styleReferencesApi.generateStyleReference).toHaveBeenCalledWith("project-1", "character");
    expect(store.activeCharacterStyleReferenceJobId).toBe("job-character");
  });

  it("starts scene style reference job", async () => {
    vi.spyOn(styleReferencesApi, "generateStyleReference").mockResolvedValue({ job_id: "job-scene", sub_job_ids: [] });
    const store = useWorkbenchStore();
    store.current = { id: "project-1", stage_raw: "characters_locked" } as never;

    await store.generateStyleReference("scene");

    expect(styleReferencesApi.generateStyleReference).toHaveBeenCalledWith("project-1", "scene");
    expect(store.activeSceneStyleReferenceJobId).toBe("job-scene");
  });
});
