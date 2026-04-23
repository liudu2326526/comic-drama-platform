
/* frontend/tests/unit/characters.api.spec.ts */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { client } from "@/api/client";
import { charactersApi } from "@/api/characters";

describe("charactersApi request shape", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("list → GET /projects/:id/characters", async () => {
    const spy = vi.spyOn(client, "get").mockResolvedValue({ data: [] } as never);
    await charactersApi.list("pid");
    expect(spy).toHaveBeenCalledWith("/projects/pid/characters");
  });

  it("generate uses 60s timeout for extract_characters ack request", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J1", sub_job_ids: [] }
    } as never);
    const r = await charactersApi.generate("pid", { extra_hints: ["美强惨"] });
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/generate",
      { extra_hints: ["美强惨"] },
      { timeout: 60_000 }
    );
    expect(r.job_id).toBe("J1");
    expect(r.sub_job_ids).toEqual([]);
  });

  it("update → PATCH /projects/:id/characters/:cid", async () => {
    const spy = vi.spyOn(client, "patch").mockResolvedValue({ data: { id: "c1" } } as never);
    await charactersApi.update("pid", "c1", { summary: "新简介" });
    expect(spy).toHaveBeenCalledWith("/projects/pid/characters/c1", { summary: "新简介" });
  });

  it("regenerate → POST /projects/:id/characters/:cid/regenerate", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J2", sub_job_ids: [] }
    } as never);
    const r = await charactersApi.regenerate("pid", "c1");
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/c1/regenerate",
      {},
      { timeout: 60_000 }
    );
    expect(r.job_id).toBe("J2");
  });

  it("registerAsset → POST /projects/:id/characters/:cid/register_asset", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "LJ1", sub_job_ids: [] }
    } as never);
    const r = await charactersApi.registerAsset("pid", "c1");
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/c1/register_asset",
      {},
      { timeout: 30_000 }
    );
    expect(r.job_id).toBe("LJ1");
  });

  it("confirmStage → POST /projects/:id/characters/confirm", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { stage: "characters_locked", stage_raw: "characters_locked" }
    } as never);
    const r = await charactersApi.confirmStage("pid");
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/confirm",
      {},
      { timeout: 30_000 }
    );
    expect(r.stage_raw).toBe("characters_locked");
  });
});
