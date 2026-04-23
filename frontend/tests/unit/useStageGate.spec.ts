/* frontend/tests/unit/useStageGate.spec.ts */
import { describe, it, expect } from "vitest";
import { gateFlags } from "@/composables/useStageGate";

describe("gateFlags", () => {
  it("draft: only rollback is false, edit allowed", () => {
    const g = gateFlags("draft");
    expect(g.canEditStoryboards).toBe(true);
    expect(g.canGenerateCharacters).toBe(false);
    expect(g.canRollback).toBe(false);
  });

  it("storyboard_ready: edit + characters gen allowed", () => {
    const g = gateFlags("storyboard_ready");
    expect(g.canEditStoryboards).toBe(true);
    expect(g.canGenerateCharacters).toBe(true);
    expect(g.canRollback).toBe(true);
  });

  it("rendering: render allowed, export not", () => {
    const g = gateFlags("rendering");
    expect(g.canRender).toBe(true);
    expect(g.canExport).toBe(false);
    expect(g.canLockShot).toBe(true);
  });

  it("exported: all write gates false, rollback true", () => {
    const g = gateFlags("exported");
    expect(g.canEditStoryboards).toBe(false);
    expect(g.canExport).toBe(false);
    expect(g.canRollback).toBe(true);
  });

  it("null stage: all false", () => {
    const g = gateFlags(null);
    expect(g.canRollback).toBe(false);
    expect(g.canEditStoryboards).toBe(false);
  });

  describe("M3a gates", () => {
    it("storyboard_ready: can edit/generate characters and入人像库, not scenes", () => {
      const f = gateFlags("storyboard_ready");
      expect(f.canEditCharacters).toBe(true);
      expect(f.canRegisterCharacterAsset).toBe(true);
      expect(f.canConfirmCharacters).toBe(true);
      expect(f.canGenerateCharacters).toBe(true);
      expect(f.canEditScenes).toBe(false);
      expect(f.canBindScene).toBe(false);
      expect(f.canConfirmScenes).toBe(false);
      expect(f.canGenerateScenes).toBe(false);
    });

    it("characters_locked: can edit/generate scenes and confirm render stage, while still allowing入人像库", () => {
      const f = gateFlags("characters_locked");
      expect(f.canEditCharacters).toBe(false);
      expect(f.canRegisterCharacterAsset).toBe(true);
      expect(f.canConfirmCharacters).toBe(false);
      expect(f.canGenerateCharacters).toBe(false);
      expect(f.canEditScenes).toBe(true);
      expect(f.canBindScene).toBe(true);
      expect(f.canConfirmScenes).toBe(true);
      expect(f.canGenerateScenes).toBe(true);
      expect(f.canRender).toBe(false);
    });

    it("scenes_locked and later: character/scene edits stay closed, but入人像库 remains available", () => {
      const raws = ["scenes_locked", "rendering", "ready_for_export", "exported"] as const;
      for (const r of raws) {
        const f = gateFlags(r);
        expect(f.canEditCharacters).toBe(false);
        expect(f.canEditScenes).toBe(false);
        expect(f.canRegisterCharacterAsset).toBe(true);
        expect(f.canConfirmScenes).toBe(false);
        expect(f.canBindScene).toBe(false);
      }
    });
  });
});
