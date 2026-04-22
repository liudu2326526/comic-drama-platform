<script setup lang="ts">
import { storeToRefs } from "pinia";

import PanelSection from "@/components/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { currentProject } = storeToRefs(store);
</script>

<template>
  <PanelSection kicker="导出" title="导出短视频与任务状态">
    <template #actions>
      <span class="tag success">镜头完整性通过</span>
      <button class="primary-btn" type="button">导出 MP4</button>
    </template>

    <div class="export-layout">
      <div class="export-summary">
        <article class="export-card">
          <span>导出配置</span>
          <ul>
            <li v-for="item in currentProject.exportConfig" :key="item">{{ item }}</li>
          </ul>
        </article>

        <article class="export-card">
          <span>时间轴预览</span>
          <div class="timeline">
            <i v-for="index in 6" :key="index" :style="{ width: `${6 + index}%` }"></i>
          </div>
          <p>{{ currentProject.exportDuration }}</p>
        </article>
      </div>

      <div class="export-task">
        <div class="task-head">
          <strong>导出任务队列</strong>
          <span>最近更新 18:12</span>
        </div>

        <article v-for="task in currentProject.exportTasks" :key="task.id" class="task-row">
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
