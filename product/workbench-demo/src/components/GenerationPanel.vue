<script setup lang="ts">
import { storeToRefs } from "pinia";

import PanelSection from "@/components/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { currentProject } = storeToRefs(store);
</script>

<template>
  <PanelSection kicker="镜头生成页" title="镜头生成队列与结果预览">
    <template #actions>
      <span class="tag success">{{ currentProject.generationProgress }}</span>
      <button class="primary-btn" type="button">批量继续生成</button>
    </template>

    <div class="generation-layout">
      <div class="generation-queue">
        <article
          v-for="item in currentProject.generationQueue"
          :key="item.id"
          class="queue-item"
          :class="{ active: item.id === currentProject.generationQueue[0]?.id }"
        >
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.summary }}</p>
          </div>
          <span class="status" :class="item.status">
            {{
              item.status === "success"
                ? "已完成"
                : item.status === "processing"
                  ? "生成中"
                  : "待重试"
            }}
          </span>
        </article>
      </div>

      <div class="generation-preview">
        <div class="preview-frame">
          <div class="frame-caption">
            <span>Frame Preview</span>
            <strong>{{ currentProject.generationQueue[0]?.title }} 最终候选</strong>
          </div>
          <div class="frame-scene">
            <div class="preview-moon"></div>
            <div class="preview-wall"></div>
            <div class="preview-character"></div>
            <div class="preview-well"></div>
          </div>
        </div>

        <div class="preview-notes">
          <article>
            <span>使用输入</span>
            <p>{{ currentProject.generationNotes.input }}</p>
          </article>
          <article>
            <span>生成建议</span>
            <p>{{ currentProject.generationNotes.suggestion }}</p>
          </article>
        </div>
      </div>
    </div>
  </PanelSection>
</template>
