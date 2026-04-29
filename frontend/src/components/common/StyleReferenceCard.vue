<script setup lang="ts">
import { computed } from "vue";
import type { StyleReferenceKind, StyleReferenceState } from "@/types";

const props = defineProps<{
  kind: StyleReferenceKind;
  state: StyleReferenceState;
  disabled: boolean;
  running: boolean;
}>();

defineEmits<{
  generate: [];
  cancelGenerate: [];
}>();

const title = computed(() =>
  props.kind === "character" ? "统一角色形象参考图" : "统一场景视觉参考图"
);
const eyebrow = computed(() => (props.kind === "character" ? "Character Style" : "Scene Style"));
const placeholder = computed(() => (props.kind === "character" ? "白底正面全身形象" : "无人物场景视觉"));
const hint = computed(() =>
  props.kind === "character"
    ? "用于统一人物比例、画风、服装质感和白底全身形象。"
    : "用于统一空间结构、色彩光影、建筑材质和时代氛围；画面中不允许出现人物。"
);
const actionLabel = computed(() => {
  if (props.running || props.state.status === "running") return "生成中...";
  if (props.state.imageUrl) return "重新生成";
  if (props.state.status === "failed") return "重试";
  return "生成参考图";
});
</script>

<template>
  <section class="style-reference-card">
    <header class="style-reference-card__header">
      <div>
        <p class="style-reference-card__eyebrow">{{ eyebrow }}</p>
        <h3>{{ title }}</h3>
      </div>
      <button type="button" :disabled="disabled || running" @click="$emit('generate')">
        {{ actionLabel }}
      </button>
      <button v-if="running" type="button" @click="$emit('cancelGenerate')">
        取消生成
      </button>
    </header>

    <div class="style-reference-card__preview" :class="{ 'is-empty': !state.imageUrl }">
      <img v-if="state.imageUrl" :src="state.imageUrl" :alt="title" />
      <div v-else class="style-reference-card__placeholder">{{ placeholder }}</div>
    </div>

    <div v-if="running || state.status === 'running'" class="style-reference-card__progress">
      <span>正在生成...</span>
      <div class="style-reference-card__bar"><i /></div>
    </div>
    <p v-if="state.error" class="style-reference-card__error">{{ state.error }}</p>
    <p class="style-reference-card__hint">{{ hint }}</p>
  </section>
</template>

<style scoped>
.style-reference-card {
  min-height: 100%;
  padding: 18px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
  background:
    radial-gradient(circle at top right, rgba(201, 169, 92, 0.12), transparent 36%),
    rgba(255, 255, 255, 0.03);
}

.style-reference-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.style-reference-card__eyebrow {
  margin: 0 0 6px;
  color: var(--accent);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.style-reference-card h3 {
  margin: 0;
  font-size: 18px;
}

.style-reference-card button {
  border: 1px solid var(--panel-border);
  border-radius: 999px;
  padding: 7px 12px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-main);
  cursor: pointer;
}

.style-reference-card button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.style-reference-card__preview {
  position: relative;
  min-height: 190px;
  overflow: hidden;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  background: rgba(12, 16, 29, 0.72);
}

.style-reference-card__preview img {
  width: 100%;
  height: 100%;
  min-height: 190px;
  object-fit: cover;
  display: block;
}

.style-reference-card__placeholder {
  display: grid;
  min-height: 190px;
  place-items: center;
  color: var(--text-faint);
  font-size: 13px;
}

.style-reference-card__progress {
  margin-top: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.style-reference-card__bar {
  height: 5px;
  margin-top: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.style-reference-card__bar i {
  display: block;
  width: 42%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), rgba(255, 255, 255, 0.8));
  animation: style-ref-loading 1.2s ease-in-out infinite alternate;
}

.style-reference-card__error {
  margin: 12px 0 0;
  color: var(--danger);
  font-size: 13px;
}

.style-reference-card__hint {
  margin: 12px 0 0;
  color: var(--text-faint);
  font-size: 13px;
  line-height: 1.6;
}

@keyframes style-ref-loading {
  from { transform: translateX(-20%); }
  to { transform: translateX(160%); }
}
</style>
