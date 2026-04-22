<!-- frontend/src/components/scene/SceneEditorModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "@/components/common/Modal.vue";
import type { SceneUpdate } from "@/types/api";
import type { SceneAsset } from "@/types";

const props = defineProps<{
  open: boolean;
  scene: SceneAsset | null;
  busy?: boolean;
}>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: SceneUpdate): void;
}>();

const name = ref("");
const theme = ref("");
const summary = ref("");
const description = ref("");
const validationError = ref<string | null>(null);

watch(
  () => props.open,
  (open) => {
    if (open && props.scene) {
      name.value = props.scene.name;
      theme.value = props.scene.theme ?? "";
      summary.value = props.scene.summary ?? "";
      description.value = props.scene.description ?? "";
      validationError.value = null;
    }
  },
  { immediate: true }
);

const canSubmit = computed(() => !!name.value.trim() && !props.busy);

function submit() {
  const trimmedName = name.value.trim();
  if (!trimmedName) {
    validationError.value = "名称不能为空";
    return;
  }
  if (trimmedName.length > 64) {
    validationError.value = "名称不能超过 64 字";
    return;
  }
  const payload: SceneUpdate = {
    name: trimmedName,
    summary: summary.value.trim() || null,
    description: description.value.trim() || null
  };
  // 后端 SceneUpdate.theme 不接受显式 null,但接受空串
  payload.theme = theme.value.trim();
  emit("submit", payload);
}
</script>

<template>
  <Modal :open="open" title="编辑场景" @close="emit('close')">
    <form class="scene-form" @submit.prevent="submit">
      <label>
        <span>场景名</span>
        <input v-model="name" type="text" maxlength="64" required />
      </label>
      <label>
        <span>主题(可选)</span>
        <input v-model="theme" type="text" maxlength="32" placeholder="palace / academy / harbor / …" />
      </label>
      <label>
        <span>简介(255 字以内)</span>
        <input v-model="summary" type="text" maxlength="255" />
      </label>
      <label>
        <span>详细描述</span>
        <textarea v-model="description" rows="5" />
      </label>
      <p v-if="validationError" class="form-error">{{ validationError }}</p>
      <div class="form-actions">
        <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
        <button class="primary-btn" type="submit" :disabled="!canSubmit">
          {{ busy ? "保存中..." : "保存" }}
        </button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.scene-form { display: flex; flex-direction: column; gap: 14px; }
.scene-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.scene-form input, .scene-form textarea {
  padding: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}
.form-error { color: var(--danger); font-size: 12px; margin: 0; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
</style>
