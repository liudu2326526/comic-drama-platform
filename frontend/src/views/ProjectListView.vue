<!-- frontend/src/views/ProjectListView.vue -->
<script setup lang="ts">
import { onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import { useProjectsStore } from "@/store/projects";
import { useToast } from "@/composables/useToast";
import { confirm } from "@/composables/useConfirm";
import { ApiError, messageFor } from "@/utils/error";

const store = useProjectsStore();
const { filtered, loading, keyword, metrics } = storeToRefs(store);
const router = useRouter();
const toast = useToast();

onMounted(async () => {
  try {
    await store.fetchList();
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "加载失败");
  }
});

async function remove(id: string, name: string) {
  const ok = await confirm({
    title: "删除项目?",
    body: `「${name}」的所有镜头、资产、导出任务将一并删除。`,
    confirmText: "确认删除",
    danger: true
  });
  if (!ok) return;
  try {
    await store.deleteProject(id);
    toast.success("已删除");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "删除失败");
  }
}
</script>

<template>
  <div class="page-shell">
    <AppTopbar title="我的项目" subtitle="管理所有漫剧项目">
      <button class="primary-btn" @click="$router.push({ name: 'project-new' })">新建项目</button>
    </AppTopbar>

    <section class="list-head">
      <input v-model="keyword" placeholder="按名称搜索" class="search" />
      <div class="metrics">
        <span v-for="m in metrics" :key="m.label">
          <b>{{ m.value }}</b> {{ m.label }}
        </span>
      </div>
    </section>

    <section class="project-grid">
      <article
        v-for="p in filtered"
        :key="p.id"
        class="project-card"
        @click="router.push({ name: 'workbench', params: { id: p.id } })"
      >
        <header>
          <span class="stage">{{ p.stage }}</span>
          <h3>{{ p.name }}</h3>
        </header>
        <p class="meta">
          {{ p.storyboard_count }} 个镜头 · {{ p.character_count }} 角色 ·
          {{ p.scene_count }} 场景
        </p>
        <footer>
          <time>{{ new Date(p.updated_at).toLocaleString("zh-CN") }}</time>
          <button class="danger-link" @click.stop="remove(p.id, p.name)">删除</button>
        </footer>
      </article>
      <p v-if="!loading && !filtered.length" class="empty">暂无项目,从右上角新建</p>
      <p v-if="loading" class="empty">正在加载...</p>
    </section>
  </div>
</template>

<style scoped>
.list-head {
  display: flex;
  justify-content: space-between;
  margin: 18px 0 24px;
  gap: 18px;
  align-items: center;
}
.search {
  flex: 0 0 280px;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
}
.metrics {
  display: flex;
  gap: 24px;
  color: var(--text-muted);
  font-size: 13px;
}
.metrics b {
  color: var(--text-primary);
  margin-right: 4px;
}
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}
.project-card {
  padding: 20px;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all 160ms;
}
.project-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}
.project-card .stage {
  font-size: 12px;
  color: var(--accent);
  font-weight: 600;
}
.project-card h3 {
  margin: 8px 0 12px;
  color: var(--text-primary);
  font-size: 18px;
}
.project-card .meta {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0 0 16px;
}
.project-card footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-faint);
  padding-top: 12px;
  border-top: 1px solid var(--panel-border);
}
.danger-link {
  color: var(--danger);
  font-size: 12px;
  font-weight: 600;
}
.danger-link:hover {
  text-decoration: underline;
}
.empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--text-faint);
  padding: 60px 0;
}
</style>
