/* frontend/src/store/projects.ts */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { projectsApi } from "@/api/projects";
import type { ProjectCreateRequest, ProjectSummary } from "@/types/api";
import { isApiError } from "@/utils/error";

export const useProjectsStore = defineStore("projects", () => {
  const list = ref<ProjectSummary[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const keyword = ref("");

  const filtered = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) return list.value;
    return list.value.filter((p) => p.name.toLowerCase().includes(kw));
  });

  const metrics = computed(() => [
    { label: "项目总数", value: `${total.value} 个` },
    {
      label: "待导出",
      value: `${list.value.filter((p) => p.stage_raw === "ready_for_export").length} 个`
    },
    { label: "已完成", value: `${list.value.filter((p) => p.stage_raw === "exported").length} 个` }
  ]);

  async function fetchList(page = 1, pageSize = 50) {
    loading.value = true;
    try {
      const resp = await projectsApi.list({ page, page_size: pageSize });
      list.value = resp.items;
      total.value = resp.total;
    } finally {
      loading.value = false;
    }
  }

  async function createProject(payload: ProjectCreateRequest) {
    const resp = await projectsApi.create(payload);
    await fetchList();
    return resp;
  }

  async function deleteProject(id: string) {
    await projectsApi.remove(id);
    list.value = list.value.filter((p) => p.id !== id);
    total.value = Math.max(0, total.value - 1);
  }

  function applyFilter(kw: string) {
    keyword.value = kw;
  }

  return {
    list,
    total,
    loading,
    keyword,
    filtered,
    metrics,
    fetchList,
    createProject,
    deleteProject,
    applyFilter,
    isApiError
  };
});
