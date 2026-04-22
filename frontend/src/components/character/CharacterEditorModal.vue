<!-- frontend/src/components/character/CharacterEditorModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "@/components/common/Modal.vue";
import type { CharacterRoleType, CharacterUpdate } from "@/types/api";
import type { CharacterAsset } from "@/types";

const props = defineProps<{
  open: boolean;
  character: CharacterAsset | null;
  busy?: boolean;
}>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: CharacterUpdate): void;
}>();

const ROLE_OPTIONS: { value: CharacterRoleType; label: string }[] = [
  { value: "protagonist", label: "主角" },
  { value: "supporting", label: "配角" },
  { value: "atmosphere", label: "氛围" }
];

const name = ref("");
const roleType = ref<CharacterRoleType>("supporting");
const summary = ref("");
const description = ref("");
const validationError = ref<string | null>(null);

watch(
  () => props.open,
  (open) => {
    if (open && props.character) {
      name.value = props.character.name;
      roleType.value = (props.character.role_type ?? "supporting") as CharacterRoleType;
      summary.value = props.character.summary ?? "";
      description.value = props.character.description ?? "";
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
  const payload: CharacterUpdate = {};
  if (trimmedName !== props.character?.name) payload.name = trimmedName;
  if (roleType.value !== props.character?.role_type) payload.role_type = roleType.value;
  
  const trimmedSummary = summary.value.trim() || null;
  if (trimmedSummary !== (props.character?.summary ?? null)) payload.summary = trimmedSummary;
  
  const trimmedDesc = description.value.trim() || null;
  if (trimmedDesc !== (props.character?.description ?? null)) payload.description = trimmedDesc;

  if (Object.keys(payload).length === 0) {
    emit("close");
    return;
  }
  emit("submit", payload);
}
</script>

<template>
  <Modal :open="open" title="编辑角色" @close="emit('close')">
    <form class="character-form" @submit.prevent="submit">
      <label>
        <span>角色名</span>
        <input v-model="name" type="text" maxlength="64" required />
      </label>
      <label>
        <span>角色类型</span>
        <select v-model="roleType">
          <option v-for="opt in ROLE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
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
.character-form { display: flex; flex-direction: column; gap: 14px; }
.character-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.character-form input, .character-form select, .character-form textarea {
  padding: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}
.form-error { color: var(--danger); font-size: 12px; margin: 0; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
</style>
