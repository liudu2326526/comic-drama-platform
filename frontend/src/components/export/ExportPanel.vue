<!-- frontend/src/components/export/ExportPanel.vue -->
<script setup lang="ts">
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { current } = storeToRefs(store);
</script>

<template>
  <PanelSection v-if="current" kicker="06" title="导出">
    <template #actions>
      <button class="primary-btn" type="button" disabled>导出 MP4</button>
    </template>

    <div v-if="!current.exportTasks.length" class="empty-note">
      尚未开始导出 · 所有镜头生成后可开始导出短视频
    </div>
    <div v-else class="export-layout">
      <div class="export-summary">
        <article class="export-card">
          <span>导出配置</span>
          <ul>
            <li v-for="item in current.exportConfig" :key="item">{{ item }}</li>
          </ul>
        </article>

        <article class="export-card">
          <span>时间轴预览</span>
          <div class="timeline">
            <i v-for="index in 6" :key="index" :style="{ width: `${6 + index}%` }" />
          </div>
          <p>{{ current.exportDuration }}</p>
        </article>
      </div>

      <div class="export-task">
        <div class="task-head">
          <strong>导出任务队列</strong>
          <span>最近更新 18:12</span>
        </div>

        <article v-for="task in current.exportTasks" :key="task.id" class="task-row">
          <div>
            <strong>{{ task.name }}</strong>
            <p>{{ task.summary }}</p>
          </div>
          <span class="status" :class="task.status">{{ task.progressLabel }}</span>
        </article>
      </div>
    </div>
  </PanelSection>
</template>

<style scoped>
.export-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 20px;
}
.export-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.export-card {
  padding: 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.export-card span {
  display: block;
  font-size: 12px;
  color: var(--text-faint);
  margin-bottom: 12px;
}
.export-card ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
}
.timeline {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  margin-bottom: 12px;
}
.timeline i {
  height: 30px;
  background: var(--accent-dim);
  border: 1px solid var(--accent);
  border-radius: 4px;
}
.export-task {
  padding: 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.task-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--panel-border);
}
.task-head strong {
  font-size: 15px;
}
.task-head span {
  font-size: 12px;
  color: var(--text-faint);
}
.task-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  margin-bottom: 10px;
}
.task-row strong {
  display: block;
  font-size: 14px;
  margin-bottom: 4px;
}
.task-row p {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
.status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
}
.status.success {
  color: var(--success);
}
.empty-note {
  padding: 40px 0;
  text-align: center;
  color: var(--text-faint);
  font-size: 14px;
}
</style>
