<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";

import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { projects, currentProjectId, sidebarMetrics } = storeToRefs(store);

const keyword = ref("");

const filteredProjects = computed(() => {
  if (!keyword.value.trim()) {
    return projects.value;
  }

  const normalizedKeyword = keyword.value.trim();

  return projects.value.filter(
    (project) =>
      project.name.includes(normalizedKeyword) ||
      project.stage.includes(normalizedKeyword) ||
      project.genre.includes(normalizedKeyword)
  );
});
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-head">
      <p class="sidebar-title">项目列表</p>
      <button class="icon-btn" type="button" aria-label="新建项目">+</button>
    </div>

    <label class="search-box">
      <span>检索项目 / 角色 / 场景</span>
      <input v-model="keyword" type="text" placeholder="输入项目名或风格关键字" />
    </label>

    <div class="project-list">
      <button
        v-for="project in filteredProjects"
        :key="project.id"
        class="project-card"
        :class="{ active: currentProjectId === project.id }"
        type="button"
        @click="store.selectProject(project.id)"
      >
        <span class="project-card-stage">{{ project.stage }}</span>
        <strong>{{ project.name }}</strong>
        <small>
          {{ project.storyboards.length }} 个镜头 · {{ project.characters.length }} 角色资产 ·
          {{ project.scenes.length }} 场景资产
        </small>
      </button>
    </div>

    <section class="sidebar-metrics">
      <article v-for="metric in sidebarMetrics" :key="metric.label">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
      </article>
    </section>
  </aside>
</template>
