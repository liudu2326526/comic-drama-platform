/* frontend/tests/unit/useJobPolling.spec.ts */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ref } from "vue";
import { useJobPolling } from "@/composables/useJobPolling";
import type { JobState } from "@/types/api";

const baseJob: JobState = {
  id: "j1",
  kind: "parse_novel",
  status: "running",
  progress: 10,
  total: 100,
  done: 10,
  result: null,
  error_msg: null,
  created_at: "",
  finished_at: null
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useJobPolling", () => {
  it("polls at 2s, stops on success terminal state", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ...baseJob, progress: 30 })
      .mockResolvedValueOnce({ ...baseJob, progress: 60 })
      .mockResolvedValueOnce({ ...baseJob, status: "succeeded", progress: 100 });
    const onSuccess = vi.fn();
    const onError = vi.fn();

    const jobId = ref<string | null>("j1");
    useJobPolling(jobId, { onSuccess, onError }, fetcher);

    await vi.advanceTimersByTimeAsync(2100);
    await vi.advanceTimersByTimeAsync(2100);
    await vi.advanceTimersByTimeAsync(2100);

    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(onSuccess).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("backs off 2s -> 4s -> 8s when no progress", async () => {
    const same = { ...baseJob };
    const fetcher = vi.fn().mockResolvedValue(same);
    const jobId = ref<string | null>("j1");
    useJobPolling(jobId, { onSuccess: () => {}, onError: () => {} }, fetcher);

    // 1st tick (2s)
    await vi.advanceTimersByTimeAsync(2100);
    expect(fetcher).toHaveBeenCalledTimes(1);

    // 2nd tick (2s)
    await vi.advanceTimersByTimeAsync(2100);
    expect(fetcher).toHaveBeenCalledTimes(2);

    // 3rd tick (2s)
    await vi.advanceTimersByTimeAsync(2100);
    expect(fetcher).toHaveBeenCalledTimes(3);

    // Now sameCount=3, stage becomes 1 (4s)
    await vi.advanceTimersByTimeAsync(4100);
    expect(fetcher).toHaveBeenCalledTimes(4);

    await vi.advanceTimersByTimeAsync(4100);
    expect(fetcher).toHaveBeenCalledTimes(5);

    await vi.advanceTimersByTimeAsync(4100);
    expect(fetcher).toHaveBeenCalledTimes(6);

    // Now sameCount=3 again, stage becomes 2 (8s)
    await vi.advanceTimersByTimeAsync(8100);
    expect(fetcher).toHaveBeenCalledTimes(7);
  });

  it("null jobId stops polling", async () => {
    const fetcher = vi.fn().mockResolvedValue(baseJob);
    const jobId = ref<string | null>("j1");
    const { cancel } = useJobPolling(jobId, { onSuccess: () => {}, onError: () => {} }, fetcher);

    await vi.advanceTimersByTimeAsync(2100);
    expect(fetcher).toHaveBeenCalledTimes(1);
    
    cancel();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
