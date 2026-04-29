<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { PromptProfileState } from "@/types/api";

const props = defineProps<{
  title: string;
  description: string;
  profile: PromptProfileState;
  editable: boolean;
  generating?: boolean;
  generateJobLabel?: string | null;
  generateError?: string | null;
  submitting?: boolean;
}>();

const emit = defineEmits<{
  generate: [];
  cancelGenerate: [];
  save: [prompt: string];
  clear: [];
  restore: [];
  confirm: [];
  skip: [];
}>();

const promptText = ref("");

watch(
  () => props.profile,
  (profile) => {
    promptText.value = profile.draft?.prompt ?? profile.applied?.prompt ?? "";
  },
  { immediate: true, deep: true }
);

const normalizedCurrentDraft = computed(() => props.profile.draft?.prompt?.trim() ?? "");
const normalizedPromptText = computed(() => promptText.value.trim());
const canSave = computed(
  () => props.editable && !!normalizedPromptText.value && normalizedPromptText.value !== normalizedCurrentDraft.value
);
const statusLabel = computed(() => {
  switch (props.profile.status) {
    case "draft_only":
      return "草稿未应用";
    case "applied":
      return "已应用";
    case "dirty":
      return "已修改未应用";
    default:
      return "未配置";
  }
});
const sourceLabel = computed(() => {
  const source = props.profile.draft?.source ?? props.profile.applied?.source;
  if (source === "ai") return "AI 建议";
  if (source === "manual") return "手动维护";
  return "等待配置";
});

function saveDraft() {
  if (!canSave.value) return;
  emit("save", normalizedPromptText.value);
}
</script>

<template>
  <section class="prompt-profile-card">
    <div class="card-head">
      <div>
        <p class="panel-kicker">统一视觉设定</p>
        <h3>{{ title }}</h3>
        <p class="description">{{ description }}</p>
      </div>
      <div class="status-group">
        <span class="status-pill">{{ statusLabel }}</span>
        <span class="source-pill">{{ sourceLabel }}</span>
      </div>
    </div>

    <div v-if="generating" class="job-banner running">
      <strong>{{ generateJobLabel || "正在生成统一视觉设定…" }}</strong>
      <button class="ghost-btn small" type="button" @click="emit('cancelGenerate')">取消生成</button>
    </div>
    <div v-else-if="generateError" class="job-banner error">
      <strong>生成失败</strong>
      <p>{{ generateError }}</p>
    </div>

    <textarea
      v-model="promptText"
      class="prompt-input"
      :disabled="!editable || generating || submitting"
      placeholder="补充项目统一视觉设定，例如时代、画风、镜头语言、色彩、角色/场景共性与禁止项。"
      rows="7"
      data-testid="prompt-profile-input"
    />

    <div class="action-row">
      <button
        class="ghost-btn"
        type="button"
        :disabled="!editable || generating || submitting"
        @click="emit('generate')"
      >
        AI 生成建议
      </button>
      <button
        class="ghost-btn"
        type="button"
        :disabled="!canSave || generating || submitting"
        @click="saveDraft"
      >
        保存草稿
      </button>
      <button
        v-if="profile.draft"
        class="ghost-btn"
        type="button"
        :disabled="!editable || generating || submitting"
        @click="emit('clear')"
      >
        清空草稿
      </button>
      <button
        v-if="profile.status === 'dirty' && profile.applied"
        class="ghost-btn"
        type="button"
        :disabled="!editable || generating || submitting"
        data-testid="prompt-profile-restore"
        @click="emit('restore')"
      >
        恢复到已应用版本
      </button>
      <button
        v-if="profile.status === 'draft_only' || profile.status === 'dirty'"
        class="primary-btn"
        type="button"
        :disabled="!editable || generating || submitting"
        @click="emit('confirm')"
      >
        确认新配置并生成
      </button>
      <button
        v-else-if="profile.status === 'applied'"
        class="primary-btn"
        type="button"
        :disabled="!editable || generating || submitting"
        @click="emit('confirm')"
      >
        按当前配置重新生成
      </button>
      <button
        v-else
        class="primary-btn"
        type="button"
        :disabled="!editable || generating || submitting"
        @click="emit('skip')"
      >
        跳过并直接生成
      </button>
    </div>
  </section>
</template>

<style scoped>
.prompt-profile-card {
  margin-bottom: 18px;
  padding: 18px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
}

.card-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.card-head h3 {
  margin: 0 0 8px;
  font-size: 18px;
}

.description {
  margin: 0;
  color: var(--text-faint);
  font-size: 13px;
  line-height: 1.6;
}

.status-group {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.status-pill,
.source-pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}

.status-pill {
  background: var(--accent-dim);
  color: var(--accent);
}

.source-pill {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-muted);
}

.job-banner {
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.02);
}

.job-banner.error {
  border-color: var(--danger);
}

.job-banner p {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.prompt-input {
  width: 100%;
  min-height: 152px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--panel-border);
  background: rgba(12, 16, 29, 0.86);
  color: var(--text-main);
  font: inherit;
  line-height: 1.6;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}
</style>
