<!-- frontend/src/components/storyboard/StoryboardEditorModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "@/components/common/Modal.vue";
import type { StoryboardShot } from "@/types";
import type { StoryboardCreateRequest, StoryboardUpdateRequest } from "@/types/api";

const props = defineProps<{
  open: boolean;
  mode: "create" | "edit";
  initial?: StoryboardShot | null;
}>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: StoryboardCreateRequest | StoryboardUpdateRequest): void;
}>();

const title = ref("");
const description = ref("");
const detail = ref("");
const durationSec = ref<number | null>(null);
const tagsInput = ref("");
const submitting = ref(false);

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    submitting.value = false;
    if (props.mode === "edit" && props.initial) {
      title.value = props.initial.title;
      description.value = props.initial.description;
      detail.value = props.initial.detail ?? "";
      durationSec.value = props.initial.duration_sec;
      tagsInput.value = (props.initial.tags ?? []).join(", ");
    } else {
      title.value = "";
      description.value = "";
      detail.value = "";
      durationSec.value = null;
      tagsInput.value = "";
    }
  },
  { immediate: true }
);

const durationError = computed(() => {
  const v = durationSec.value;
  if (v === null) return "";
  if (Number.isNaN(v)) return "时长必须是数字";
  if (v < 0 || v > 300) return "时长范围 0–300 秒";
  return "";
});
const titleError = computed(() => {
  if (title.value.length > 128) return "标题最长 128 字";
  return "";
});

const canSubmit = computed(
  () => !durationError.value && !titleError.value && !submitting.value
);

function parsedTags(): string[] {
  return tagsInput.value
    .split(/[,，]/)
    .map((t) => t.trim())
    .filter(Boolean);
}

function tagsChanged(orig: string[] | null | undefined, next: string[]): boolean {
  return JSON.stringify(orig ?? []) !== JSON.stringify(next);
}

function onSubmit() {
  if (!canSubmit.value) return;
  submitting.value = true;
  const tags = parsedTags();
  if (props.mode === "create") {
    const payload: StoryboardCreateRequest = {
      title: title.value.trim(),
      description: description.value,
      detail: detail.value === "" ? null : detail.value,
      duration_sec: durationSec.value,
      tags: tags.length > 0 ? tags : null
    };
    emit("submit", payload);
  } else {
    // edit:只发送改动的字段(显式 undefined 即不发)
    const payload: StoryboardUpdateRequest = {};
    if (props.initial) {
      if (title.value !== props.initial.title) payload.title = title.value.trim();
      if (description.value !== props.initial.description) payload.description = description.value;
      const origDetail = props.initial.detail ?? "";
      if (detail.value !== origDetail) payload.detail = detail.value === "" ? null : detail.value;
      // duration_sec 后端 PATCH 禁止显式 null(_reject_explicit_null);
      // 仅在用户"明确填了一个新数字"时下发。清空时不发送,UI 已在 template 里给出提示。
      const origDuration = props.initial.duration_sec;
      if (durationSec.value !== null && durationSec.value !== origDuration) {
        payload.duration_sec = durationSec.value;
      }
      if (tagsChanged(props.initial.tags, tags)) payload.tags = tags;
    }
    emit("submit", payload);
  }
}
</script>

<template>
  <Modal :open="open" :title="mode === 'create' ? '新增镜头' : '编辑镜头'" @close="emit('close')">
    <form class="storyboard-form" @submit.prevent="onSubmit">
      <label>
        <span>镜头标题</span>
        <input v-model="title" maxlength="128" placeholder="如:皇城夜雨,山雨欲来" />
        <em v-if="titleError" class="err">{{ titleError }}</em>
      </label>
      <label>
        <span>文案描述</span>
        <textarea v-model="description" rows="3" />
      </label>
      <label>
        <span>镜头细节(可空)</span>
        <textarea v-model="detail" rows="4" />
      </label>
      <div class="form-row">
        <label>
          <span>时长(秒, 0–300, 可空)</span>
          <input v-model.number="durationSec" type="number" min="0" max="300" step="0.1" />
          <em v-if="durationError" class="err">{{ durationError }}</em>
          <em v-if="mode === 'edit' && initial && initial.duration_sec && durationSec === null" class="hint">
            时长不可清空,如需重置请先保存其他修改,下一版会放开清空支持
          </em>
        </label>
        <label>
          <span>标签(逗号分隔)</span>
          <input v-model="tagsInput" placeholder="古风, 夜景, 中景" />
        </label>
      </div>
    </form>
    <template #footer>
      <button class="ghost-btn" @click="emit('close')">取消</button>
      <button class="primary-btn" :disabled="!canSubmit" @click="onSubmit">
        {{ mode === "create" ? "新增" : "保存" }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.storyboard-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.storyboard-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}
.storyboard-form input,
.storyboard-form textarea {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font: inherit;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.err {
  color: var(--danger);
  font-size: 12px;
  font-style: normal;
}
.hint {
  color: var(--warning);
  font-size: 12px;
  font-style: normal;
}
.primary-btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: none;
  background: var(--accent);
  color: #0b0d1a;
  font-weight: 600;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ghost-btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  cursor: pointer;
}
</style>
