
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

  it("generate → POST /projects/:id/characters/generate with body", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J1", sub_job_ids: ["s1", "s2"] }
    } as never);
    const r = await charactersApi.generate("pid", { extra_hints: ["美强惨"] });
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/generate",
      { extra_hints: ["美强惨"] },
      { timeout: 60_000 }
    );
    expect(r.job_id).toBe("J1");
    expect(r.sub_job_ids).toEqual(["s1", "s2"]);
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

  it("lock(async) → POST /projects/:id/characters/:cid/lock with as_protagonist=true returns ack=async + job_id", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { ack: "async", job_id: "LJ1", sub_job_ids: [] }
    } as never);
    const r = await charactersApi.lock("pid", "c1", { as_protagonist: true });
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/c1/lock",
      { as_protagonist: true },
      { timeout: 30_000 }
    );
    expect(r.ack).toBe("async");
    if (r.ack === "async") expect(r.job_id).toBe("LJ1");
  });

  it("lock(sync) → POST /projects/:id/characters/:cid/lock with as_protagonist=false returns ack=sync + locked", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { ack: "sync", id: "c1", locked: true, is_protagonist: false }
    } as never);
    const r = await charactersApi.lock("pid", "c1", { as_protagonist: false });
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/characters/c1/lock",
      { as_protagonist: false },
      { timeout: 30_000 }
    );
    expect(r.ack).toBe("sync");
    if (r.ack === "sync") expect(r.locked).toBe(true);
  });
});
