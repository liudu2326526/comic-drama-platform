<script setup lang="ts">
import Modal from "@/components/common/Modal.vue";
import type { ShotVideoVersionRead } from "@/types/api";

defineProps<{
  open: boolean;
  versions: ShotVideoVersionRead[];
  currentRenderId: string | null;
  loading?: boolean;
}>();

defineEmits<{
  (e: "close"): void;
  (e: "select", renderId: string): void;
}>();
</script>

<template>
  <Modal :open="open" title="历史版本" @close="$emit('close')">
    <div v-if="loading" class="modal-empty">正在加载历史版本…</div>
    <div v-else-if="!versions.length" class="modal-empty">当前镜头还没有历史版本。</div>
    <div v-else class="version-list">
      <article v-for="item in versions" :key="item.id" class="version-row">
        <div class="version-copy">
          <strong>版本 v{{ item.version_no }}</strong>
          <p>{{ item.status === "succeeded" ? "已完成" : item.status }}</p>
          <small>{{ item.created_at }}</small>
          <video
            v-if="item.video_url"
            class="history-video"
            :src="item.video_url"
            preload="none"
            controls
          />
        </div>
        <button
          class="ghost-btn small"
          type="button"
          :disabled="item.id === currentRenderId"
          @click="$emit('select', item.id)"
        >
          {{ item.id === currentRenderId ? "当前版本" : "设为当前" }}
        </button>
      </article>
    </div>

    <template #footer>
      <button class="ghost-btn" type="button" @click="$emit('close')">关闭</button>
    </template>
  </Modal>
</template>

<style scoped>
.modal-empty {
  padding: 16px 0;
  color: var(--text-faint);
}
.version-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.version-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.02);
}
.version-row p {
  margin: 4px 0 0;
  color: var(--text-muted);
}
.version-copy {
  display: grid;
  gap: 6px;
}
.version-copy small {
  color: var(--text-faint);
}
.history-video {
  width: 220px;
  max-width: 100%;
  border-radius: var(--radius-sm);
}
</style>
