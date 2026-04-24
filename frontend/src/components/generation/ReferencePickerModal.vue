<script setup lang="ts">
import { computed, ref } from "vue";
import type { ReferenceAssetCreate, ReferenceCandidate, RenderSubmitReference } from "@/types/api";

const props = defineProps<{
  open: boolean;
  candidates: ReferenceCandidate[];
  selected: RenderSubmitReference[];
  maxCount?: number;
}>();

const emit = defineEmits<{
  close: [];
  add: [item: ReferenceCandidate];
  register: [payload: ReferenceAssetCreate];
}>();

const query = ref("");
const manualName = ref("");
const manualUrl = ref("");

const selectedIds = computed(() => new Set(props.selected.map((item) => item.id)));
const maxCount = computed(() => props.maxCount ?? 6);
const canAddMore = computed(() => props.selected.length < maxCount.value);
const canSubmitManual = computed(
  () => canAddMore.value && manualName.value.trim().length > 0 && manualUrl.value.trim().length > 0
);
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return props.candidates;
  return props.candidates.filter((item) =>
    [item.name, item.alias, item.kind, item.reason ?? ""].some((text) => text.toLowerCase().includes(q))
  );
});

function submitManual() {
  const name = manualName.value.trim();
  const imageUrl = manualUrl.value.trim();
  if (!name || !imageUrl) return;
  emit("register", { name, image_url: imageUrl, kind: "manual" });
  manualName.value = "";
  manualUrl.value = "";
}
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <section class="reference-picker" role="dialog" aria-modal="true" aria-label="添加参考图">
      <header>
        <strong>添加参考图</strong>
        <button class="ghost-btn small" type="button" @click="emit('close')">关闭</button>
      </header>

      <input v-model="query" class="picker-search" type="search" placeholder="搜索角色、场景、历史图" />

      <div class="candidate-grid">
        <button
          v-for="item in filtered"
          :key="item.id"
          class="candidate-card"
          type="button"
          :disabled="selectedIds.has(item.id) || !canAddMore"
          @click="emit('add', item)"
        >
          <img :src="item.image_url" :alt="item.alias" />
          <span>{{ item.alias }}</span>
          <small>{{ item.reason }}</small>
        </button>
      </div>

      <form class="manual-form" @submit.prevent="submitManual">
        <strong>项目资产图</strong>
        <input v-model="manualName" type="text" placeholder="名称" />
        <input v-model="manualUrl" type="text" placeholder="projects/{project_id}/... 或 OBS 项目 URL" />
        <button class="primary-btn" type="submit" :disabled="!canSubmitManual">加入</button>
      </form>
    </section>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.52);
}
.reference-picker {
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 64px);
  overflow: auto;
  padding: 18px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
  background: var(--panel-bg);
}
.reference-picker header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.picker-search,
.manual-form input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}
.picker-search {
  margin-top: 14px;
}
.candidate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.candidate-card {
  min-width: 0;
  padding: 8px;
  text-align: left;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-primary);
}
.candidate-card:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.candidate-card img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 6px;
}
.candidate-card span,
.candidate-card small {
  display: block;
  margin-top: 6px;
}
.candidate-card small {
  color: var(--text-faint);
}
.manual-form {
  display: grid;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--panel-border);
}
</style>
