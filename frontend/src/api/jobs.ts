/* frontend/src/api/jobs.ts */
import { client } from "./client";
import type { JobState } from "@/types/api";

export const jobsApi = {
  get(id: string, signal?: AbortSignal): Promise<JobState> {
    return client.get(`/jobs/${id}`, { signal }).then((r) => r.data as JobState);
  },
  cancel(id: string): Promise<{ id: string; status: "canceled" }> {
    return client.post(`/jobs/${id}/cancel`).then((r) => r.data as { id: string; status: "canceled" });
  }
};
