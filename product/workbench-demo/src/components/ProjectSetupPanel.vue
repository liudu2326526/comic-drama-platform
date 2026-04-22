<script setup lang="ts">
import { storeToRefs } from "pinia";

import PanelSection from "@/components/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { currentProject } = storeToRefs(store);
</script>

<template>
  <PanelSection kicker="新建项目" :title="currentProject.name">
    <template #actions>
      <span class="tag warm">{{ currentProject.genre }}</span>
      <span class="tag">{{ currentProject.ratio }}</span>
      <span class="tag">{{ currentProject.suggestedShots }}</span>
    </template>

    <div class="project-setup">
      <div class="story-input-card">
        <label>小说内容输入</label>
        <textarea :value="currentProject.story" readonly />
        <div class="input-footer">
          <span v-for="stat in currentProject.parsedStats" :key="stat">{{ stat }}</span>
        </div>
      </div>

      <div class="setup-side">
        <article class="mini-card">
          <span>项目参数</span>
          <ul>
            <li v-for="item in currentProject.setupParams" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article class="mini-card gradient-card">
          <span>AI 解析摘要</span>
          <p>{{ currentProject.summary }}</p>
        </article>
      </div>
    </div>
  </PanelSection>
</template>
