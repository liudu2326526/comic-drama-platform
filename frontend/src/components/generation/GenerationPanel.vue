<!-- frontend/src/components/generation/GenerationPanel.vue -->
<script setup lang="ts">
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { current } = storeToRefs(store);
</script>

<template>
  <PanelSection v-if="current" kicker="05" title="镜头生成">
    <template #actions>
      <span v-if="current.generationProgress" class="tag success">{{
        current.generationProgress
      }}</span>
      <button class="primary-btn" type="button" disabled>批量继续生成</button>
    </template>

    <div v-if="!current.generationQueue.length" class="empty-note">
      尚未开始生成 · 资产锁定后可开始镜头批量渲染
    </div>
    <div v-else class="generation-layout">
      <div class="generation-queue">
        <article
          v-for="item in current.generationQueue"
          :key="item.id"
          class="queue-item"
          :class="{ active: item.id === current.generationQueue[0]?.id }"
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
            <strong>{{ current.generationQueue[0]?.title }} 最终候选</strong>
          </div>
          <div class="frame-scene">
            <div class="preview-moon" />
            <div class="preview-wall" />
            <div class="preview-character" />
            <div class="preview-well" />
          </div>
        </div>

        <div v-if="current.generationNotes" class="preview-notes">
          <article>
            <span>使用输入</span>
            <p>{{ current.generationNotes.input }}</p>
          </article>
          <article>
            <span>生成建议</span>
            <p>{{ current.generationNotes.suggestion }}</p>
          </article>
        </div>
      </div>
    </div>
  </PanelSection>
</template>

<style scoped>
.generation-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 20px;
}
.generation-queue {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.queue-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.queue-item.active {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.queue-item strong {
  display: block;
  font-size: 14px;
  margin-bottom: 4px;
}
.queue-item p {
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
.status.processing {
  color: var(--warning);
}
.generation-preview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.preview-frame {
  padding: 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.frame-caption {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.frame-caption span {
  font-size: 12px;
  color: var(--text-faint);
  text-transform: uppercase;
}
.frame-caption strong {
  font-size: 14px;
}
.frame-scene {
  position: relative;
  min-height: 360px;
  background: #0b0d1a;
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.preview-moon,
.preview-wall,
.preview-character,
.preview-well {
  position: absolute;
}
.preview-moon {
  top: 40px;
  left: 40px;
  width: 50px;
  height: 60px;
  background: radial-gradient(circle, #fff, transparent);
  border-radius: 50%;
  opacity: 0.6;
}
.preview-wall {
  bottom: 60px;
  left: 20px;
  right: 20px;
  height: 80px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}
.preview-character {
  bottom: 20px;
  right: 60px;
  width: 40px;
  height: 100px;
  background: #333;
  border-radius: 20px 20px 0 0;
}
.preview-well {
  bottom: 20px;
  left: 40%;
  width: 60px;
  height: 30px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 30px 30px 0 0;
}
.preview-notes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.preview-notes article {
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.preview-notes span {
  display: block;
  font-size: 12px;
  color: var(--text-faint);
  margin-bottom: 8px;
}
.preview-notes p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}
.tag.success {
  background: rgba(92, 214, 169, 0.1);
  color: var(--success);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
}
.empty-note {
  padding: 40px 0;
  text-align: center;
  color: var(--text-faint);
  font-size: 14px;
}
</style>
