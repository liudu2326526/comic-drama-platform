/* frontend/tests/unit/storyboards.api.spec.ts */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { client } from "@/api/client";
import { storyboardsApi } from "@/api/storyboards";

vi.mock("@/api/client", () => ({
  client: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn()
  }
}));

const mocked = client as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("storyboardsApi", () => {
  it("list GETs /projects/:id/storyboards", async () => {
    mocked.get.mockResolvedValue({ data: [] });
    const out = await storyboardsApi.list("P1");
    expect(mocked.get).toHaveBeenCalledWith("/projects/P1/storyboards");
    expect(out).toEqual([]);
  });

  it("create POSTs payload as-is", async () => {
    mocked.post.mockResolvedValue({ data: { id: "S1" } });
    await storyboardsApi.create("P1", { title: "t", description: "d", idx: 2 });
    expect(mocked.post).toHaveBeenCalledWith("/projects/P1/storyboards", {
      title: "t",
      description: "d",
      idx: 2
    });
  });

  it("update PATCHes shot path with body", async () => {
    mocked.patch.mockResolvedValue({ data: { id: "S1" } });
    await storyboardsApi.update("P1", "S1", { title: "new" });
    expect(mocked.patch).toHaveBeenCalledWith("/projects/P1/storyboards/S1", {
      title: "new"
    });
  });

  it("remove DELETEs and returns deleted flag", async () => {
    mocked.delete.mockResolvedValue({ data: { deleted: true } });
    const out = await storyboardsApi.remove("P1", "S1");
    expect(mocked.delete).toHaveBeenCalledWith("/projects/P1/storyboards/S1");
    expect(out).toEqual({ deleted: true });
  });

  it("reorder POSTs ordered_ids", async () => {
    mocked.post.mockResolvedValue({ data: { reordered: 3 } });
    await storyboardsApi.reorder("P1", { ordered_ids: ["a", "b", "c"] });
    expect(mocked.post).toHaveBeenCalledWith("/projects/P1/storyboards/reorder", {
      ordered_ids: ["a", "b", "c"]
    });
  });

  it("confirm POSTs with empty body", async () => {
    mocked.post.mockResolvedValue({
      data: { stage: "storyboard_ready", stage_raw: "storyboard_ready" }
    });
    const out = await storyboardsApi.confirm("P1");
    expect(mocked.post).toHaveBeenCalledWith("/projects/P1/storyboards/confirm");
    expect(out.stage_raw).toBe("storyboard_ready");
  });
});
