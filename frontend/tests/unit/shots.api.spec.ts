import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "@/api/client";
import { shotsApi } from "@/api/shots";

describe("shotsApi request shape", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("generateRenderDraft -> POST /projects/:id/shots/:sid/render-draft", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "DJ1", sub_job_ids: [] }
    } as never);

    const resp = await shotsApi.generateRenderDraft("pid", "sid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/render-draft");
    expect(resp.job_id).toBe("DJ1");
  });

  it("getRenderDraft -> GET /projects/:id/shots/:sid/render-draft", async () => {
    const spy = vi.spyOn(client, "get").mockResolvedValue({
      data: { shot_id: "SH1", prompt: "draft", references: [] }
    } as never);

    const resp = await shotsApi.getRenderDraft("pid", "sid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/render-draft");
    expect(resp?.shot_id).toBe("SH1");
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

  it("generateVideo -> POST /projects/:id/shots/:sid/video with timeout", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "VJ1", sub_job_ids: [] }
    } as never);

    const resp = await shotsApi.generateVideo("pid", "sid", {
      prompt: "prompt",
      references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img" }],
      duration: 5,
      resolution: "720p",
      model_type: "fast"
    });

    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/shots/sid/video",
      {
        prompt: "prompt",
        references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img" }],
        duration: 5,
        resolution: "720p",
        model_type: "fast"
      },
      { timeout: 60_000 }
    );
    expect(resp.job_id).toBe("VJ1");
  });

  it("generateVideo omits duration when it is not selected", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "VJ1", sub_job_ids: [] }
    } as never);

    await shotsApi.generateVideo("pid", "sid", {
      prompt: "prompt",
      references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img" }],
      resolution: "480p",
      model_type: "fast"
    });

    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/shots/sid/video",
      {
        prompt: "prompt",
        references: [{ id: "scene-1", kind: "scene", source_id: "SC1", name: "长安殿", image_url: "https://img" }],
        resolution: "480p",
        model_type: "fast"
      },
      { timeout: 60_000 }
    );
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
      data: { shot_id: "SH1", current_video_render_id: "V2", status: "locked" }
    } as never);

    await shotsApi.lock("pid", "sid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/lock");
  });

  it("listVideos -> GET /projects/:id/shots/:sid/videos", async () => {
    const spy = vi.spyOn(client, "get").mockResolvedValue({
      data: [{ id: "V1", shot_id: "SH1", version_no: 1 }]
    } as never);

    const resp = await shotsApi.listVideos("pid", "sid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/videos");
    expect(resp[0].id).toBe("V1");
  });

  it("selectVideo -> POST /projects/:id/shots/:sid/videos/:vid/select", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { shot_id: "SH1", current_video_render_id: "V2", status: "succeeded" }
    } as never);

    await shotsApi.selectVideo("pid", "sid", "vid");

    expect(spy).toHaveBeenCalledWith("/projects/pid/shots/sid/videos/vid/select");
  });
});
