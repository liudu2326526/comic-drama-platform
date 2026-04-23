import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "@/api/client";
import { promptProfilesApi } from "@/api/promptProfiles";

describe("promptProfilesApi request shape", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("generate -> POST /projects/:id/prompt-profiles/:kind/generate", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J1", sub_job_ids: [] }
    } as never);

    const result = await promptProfilesApi.generate("pid", "character");

    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/prompt-profiles/character/generate",
      undefined,
      { timeout: 60_000 }
    );
    expect(result.job_id).toBe("J1");
  });

  it("updateDraft -> PATCH /projects/:id/prompt-profiles/:kind", async () => {
    const spy = vi.spyOn(client, "patch").mockResolvedValue({
      data: {
        draft: { prompt: "统一视觉设定", source: "manual" },
        applied: null,
        status: "draft_only"
      }
    } as never);

    const result = await promptProfilesApi.updateDraft("pid", "scene", "统一视觉设定");

    expect(spy).toHaveBeenCalledWith("/projects/pid/prompt-profiles/scene", {
      prompt: "统一视觉设定"
    });
    expect(result.status).toBe("draft_only");
  });

  it("clearDraft -> DELETE /projects/:id/prompt-profiles/:kind/draft", async () => {
    const spy = vi.spyOn(client, "delete").mockResolvedValue({
      data: {
        draft: null,
        applied: { prompt: "统一视觉设定", source: "ai" },
        status: "applied"
      }
    } as never);

    const result = await promptProfilesApi.clearDraft("pid", "character");

    expect(spy).toHaveBeenCalledWith("/projects/pid/prompt-profiles/character/draft");
    expect(result.status).toBe("applied");
  });

  it("confirm -> POST /projects/:id/prompt-profiles/:kind/confirm", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({
      data: { job_id: "J2", sub_job_ids: [] }
    } as never);

    const result = await promptProfilesApi.confirm("pid", "scene");

    expect(spy).toHaveBeenCalledWith(
      "/projects/pid/prompt-profiles/scene/confirm",
      undefined,
      { timeout: 60_000 }
    );
    expect(result.job_id).toBe("J2");
  });
});
