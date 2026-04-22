
/* frontend/tests/unit/scenes.api.spec.ts */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { client } from "@/api/client";
import { scenesApi } from "@/api/scenes";
import { storyboardsApi } from "@/api/storyboards";

describe("scenesApi request shape", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("list → GET /projects/:id/scenes", async () => {
    const spy = vi.spyOn(client, "get").mockResolvedValue({ data: [] } as never);
    await scenesApi.list("pid");
    expect(spy).toHaveBeenCalledWith("/projects/pid/scenes");
  });

  it("generate → POST /projects/:id/scenes/generate with body", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J1", sub_job_ids: [] }
    } as never);
    await scenesApi.generate("pid", { template_whitelist: ["palace"] });
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/scenes/generate",
      { template_whitelist: ["palace"] },
      { timeout: 60_000 }
    );
  });

  it("update → PATCH /projects/:id/scenes/:sid", async () => {
    const spy = vi.spyOn(client, "patch").mockResolvedValue({ data: {} } as never);
    await scenesApi.update("pid", "s1", { name: "长安殿" });
    expect(spy).toHaveBeenCalledWith("/projects/pid/scenes/s1", { name: "长安殿" });
  });

  it("regenerate → POST /projects/:id/scenes/:sid/regenerate", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J2", sub_job_ids: [] }
    } as never);
    await scenesApi.regenerate("pid", "s1");
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/scenes/s1/regenerate",
      {},
      { timeout: 60_000 }
    );
  });

  it("lock(async) → 返回 ack=async + job_id", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { ack: "async", job_id: "SJ1", sub_job_ids: [] }
    } as never);
    const r = await scenesApi.lock("pid", "s1");
    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/scenes/s1/lock",
      {},
      { timeout: 30_000 }
    );
    expect(r.ack).toBe("async");
    expect(r.job_id).toBe("SJ1");
  });
});

describe("storyboardsApi.bindScene", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("POST /projects/:id/storyboards/:shot/bind_scene with scene_id", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { shot_id: "sh1", scene_id: "sc1", scene_name: "长安殿" }
    } as never);
    const r = await storyboardsApi.bindScene("pid", "sh1", { scene_id: "sc1" });
    expect(spy).toHaveBeenCalledWith("/projects/pid/storyboards/sh1/bind_scene", {
      scene_id: "sc1"
    });
    expect(r.scene_name).toBe("长安殿");
  });
});
