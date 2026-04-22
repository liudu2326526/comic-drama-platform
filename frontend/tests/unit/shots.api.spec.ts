import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "@/api/client";
import { shotsApi } from "@/api/shots";

describe("shotsApi request shape", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renderDraft -> POST /projects/:id/shots/:sid/render-draft", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { shot_id: "SH1", prompt: "draft", references: [] }
    } as never);

    const resp = await shotsApi.renderDraft("pid", "sid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/render-draft");
    expect(resp.shot_id).toBe("SH1");
  });

  it("render -> POST /projects/:id/shots/:sid/render with timeout", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "RJ1", sub_job_ids: [] }
    } as never);

    const resp = await shotsApi.render("pid", "sid", {
      prompt: "prompt",
      references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img" }]
    });

    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/shots/sid/render",
      {
        prompt: "prompt",
        references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img" }]
      },
      { timeout: 60_000 }
    );
    expect(resp.job_id).toBe("RJ1");
  });

  it("listRenders -> GET /projects/:id/shots/:sid/renders", async () => {
    const spy = vi.spyOn(client, "get").mockResolvedValue({
      data: [{ id: "R1", shot_id: "SH1", version_no: 1 }]
    } as never);

    const resp = await shotsApi.listRenders("pid", "sid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/renders");
    expect(resp[0].id).toBe("R1");
  });

  it("selectRender -> POST /projects/:id/shots/:sid/renders/:rid/select", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { shot_id: "SH1", current_render_id: "R2", status: "succeeded" }
    } as never);

    await shotsApi.selectRender("pid", "sid", "rid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/renders/rid/select");
  });

  it("lock -> POST /projects/:id/shots/:sid/lock", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { shot_id: "SH1", current_render_id: "R2", status: "locked" }
    } as never);

    await shotsApi.lock("pid", "sid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/lock");
  });
});
