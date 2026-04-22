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
});
