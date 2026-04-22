/* frontend/src/store/jobs.ts */
import { defineStore } from "pinia";
import { reactive } from "vue";
import type { JobState } from "@/types/api";

interface Entry {
  job: JobState | null;
  cancel: () => void;
}

export const useJobsStore = defineStore("jobs", () => {
  const byId = reactive<Record<string, Entry>>({});

  function register(id: string, cancel: () => void) {
    byId[id] = { job: null, cancel };
  }
  function update(id: string, job: JobState) {
    if (byId[id]) byId[id].job = job;
  }
  function stop(id: string) {
    byId[id]?.cancel();
    delete byId[id];
  }
  function isActive(id: string) {
    return !!byId[id];
  }

  return { byId, register, update, stop, isActive };
});
