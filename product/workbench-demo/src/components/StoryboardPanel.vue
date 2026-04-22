<script setup lang="ts">
import { storeToRefs } from "pinia";

import PanelSection from "@/components/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { currentProject, currentShot, selectedShotId } = storeToRefs(store);
</script>

<template>
  <PanelSection kicker="分镜工作台" title="建议镜头数已生成，可继续合并或拆分">
    <template #actions>
      <button class="ghost-btn" type="button">智能重排节奏</button>
      <button class="primary-btn" type="button">确认 {{ currentProject.storyboards.length }} 个镜头</button>
    </template>

    <div class="storyboard-layout">
      <div class="storyboard-grid">
        <article
          v-for="shot in currentProject.storyboards"
          :key="shot.id"
          class="story-card"
          :class="{ active: selectedShotId === shot.id }"
          @click="store.selectShot(shot.id)"
        >
          <span>{{ String(shot.index).padStart(2, "0") }}</span>
          <strong>{{ shot.title }}</strong>
          <p>{{ shot.description }}</p>
        </article>
      </div>

      <div class="storyboard-detail" v-if="currentShot">
        <div class="detail-title">
          <h3>当前镜头：{{ String(currentShot.index).padStart(2, "0") }} {{ currentShot.title }}</h3>
          <span>时长建议 {{ currentShot.duration }}</span>
        </div>
        <p>{{ currentShot.detail }}</p>
        <div class="detail-tags">
          <span v-for="tag in currentShot.tags" :key="tag">{{ tag }}</span>
        </div>
      </div>
    </div>
  </PanelSection>
</template>
