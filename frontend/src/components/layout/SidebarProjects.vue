<!-- frontend/src/components/layout/SidebarProjects.vue -->
<script setup lang="ts">
import { onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import { useProjectsStore } from "@/store/projects";

const store = useProjectsStore();
const { filtered, metrics, keyword } = storeToRefs(store);
const router = useRouter();

onMounted(() => {
  void store.fetchList();
});

function open(id: string) {
  void router.push({ name: "workbench", params: { id } });
}
</script>
<template>
  <aside class="sidebar">
    <header>
      <p class="eyebrow">项目</p>
      <input v-model="keyword" placeholder="搜索项目" class="search" />
    </header>
    <ul class="project-list">
      <li v-for="p in filtered" :key="p.id" @click="open(p.id)">
        <div class="card-mini">
          <p class="name">{{ p.name }}</p>
          <p class="meta">{{ p.stage }} · {{ p.storyboard_count }} 镜头</p>
        </div>
      </li>
      <li v-if="!filtered.length" class="empty">暂无项目</li>
    </ul>
    <footer class="metrics">
      <div v-for="m in metrics" :key="m.label" class="metric">
        <span>{{ m.label }}</span>
        <strong>{{ m.value }}</strong>
      </div>
    </footer>
  </aside>
</template>
<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px;
  background: var(--panel-bg);
  border-radius: var(--radius-lg);
  border: 1px solid var(--panel-border);
  min-width: 260px;
}
.search {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
}
.project-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}
.card-mini {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 160ms;
}
.card-mini:hover {
  background: rgba(138, 140, 255, 0.08);
}
.card-mini .name {
  margin: 0 0 4px;
  font-weight: 600;
  color: var(--text-primary);
}
.card-mini .meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
.empty {
  color: var(--text-faint);
  font-size: 13px;
  padding: 12px 0;
  text-align: center;
}
.metrics {
  display: flex;
  justify-content: space-between;
  border-top: 1px solid var(--panel-border);
  padding-top: 12px;
  margin-top: auto;
}
.metric {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  color: var(--text-muted);
  gap: 2px;
}
.metric strong {
  color: var(--text-primary);
  font-size: 14px;
}
</style>
