/* frontend/src/composables/useJobPolling.ts */
import { getCurrentInstance, onUnmounted, ref, watch, type Ref } from "vue";
import { jobsApi } from "@/api/jobs";
import type { JobState } from "@/types/api";

export type JobFetcher = (id: string, signal?: AbortSignal) => Promise<JobState>;

export interface JobPollingHandlers {
  onProgress?: (job: JobState) => void;
  onSuccess: (job: JobState) => void;
  onError: (job: JobState | null, err?: unknown) => void;
}

interface JobPollingHandle {
  job: Ref<JobState | null>;
  cancel: () => void;
}

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);
const INTERVALS = [2000, 4000, 8000];
const BACKOFF_AFTER = 3;

export function useJobPolling(
  jobId: Ref<string | null>,
  handlers: JobPollingHandlers,
  fetcher: JobFetcher = jobsApi.get
): JobPollingHandle {
  const job = ref<JobState | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stage = 0;
  let sameCount = 0;
  let lastProgress = -1;
  let aborter: AbortController | null = null;

  const cancel = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (aborter) {
      aborter.abort();
      aborter = null;
    }
  };

  const tick = async (id: string) => {
    aborter = new AbortController();
    try {
      const next = await fetcher(id, aborter.signal);
      job.value = next;
      handlers.onProgress?.(next);

      if (TERMINAL.has(next.status)) {
        cancel();
        if (next.status === "succeeded") handlers.onSuccess(next);
        else handlers.onError(next);
        return;
      }

      if (next.progress === lastProgress) sameCount++;
      else {
        sameCount = 0;
        lastProgress = next.progress;
      }
      if (sameCount >= BACKOFF_AFTER && stage < INTERVALS.length - 1) {
        stage++;
        sameCount = 0;
      }
      timer = setTimeout(() => tick(id), INTERVALS[stage]);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      handlers.onError(job.value, err);
      cancel();
    }
  };

  watch(
    jobId,
    (id) => {
      cancel();
      stage = 0;
      sameCount = 0;
      lastProgress = -1;
      job.value = null;
      if (id) timer = setTimeout(() => tick(id), INTERVALS[0]);
    },
    { immediate: true }
  );

  if (getCurrentInstance()) onUnmounted(cancel);

  return { job, cancel };
}
