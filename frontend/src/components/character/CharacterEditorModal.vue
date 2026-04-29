<!-- frontend/src/components/character/CharacterEditorModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "@/components/common/Modal.vue";
import type { CharacterRoleType, CharacterUpdate, CharacterVisualType } from "@/types/api";
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
  { value: "lead", label: "主角" },
  { value: "supporting", label: "配角" },
  { value: "antagonist", label: "反派" },
  { value: "atmosphere", label: "氛围" },
  { value: "crowd", label: "群体" },
  { value: "system", label: "系统" }
];

const VISUAL_TYPE_OPTIONS: { value: CharacterVisualType; label: string; caption: string }[] = [
  { value: "human_actor", label: "真人/写实人类", caption: "需要入人像库和真人视频一致性的角色" },
  { value: "stylized_human", label: "风格化人类", caption: "动漫/插画风格的人类角色" },
  { value: "humanoid_monster", label: "类人怪物/异变人", caption: "保持人形轮廓但不按真人人像处理" },
  { value: "creature", label: "非人生命体", caption: "动物、异形、生物怪物等非人角色" },
  { value: "anomaly_entity", label: "异常体/能量体", caption: "黑雾、裂缝、能量团、不可名状异常" },
  { value: "object_entity", label: "物体/系统载体", caption: "终端、道具、系统核心、机械装置" },
  { value: "crowd_group", label: "群体角色", caption: "只生成群体风貌参考图，不生成单体头像和 360 视频" },
  { value: "environment_force", label: "环境力量/灾难源", caption: "灾害源、空间异常、环境特效类存在" }
];

const name = ref("");
const roleType = ref<CharacterRoleType>("supporting");
const visualType = ref<CharacterVisualType>("human_actor");
const summary = ref("");
const description = ref("");
const validationError = ref<string | null>(null);

watch(
  () => props.open,
  (open) => {
    if (open && props.character) {
      name.value = props.character.name;
      roleType.value = props.character.role_type ?? "supporting";
      visualType.value = props.character.visual_type ?? "human_actor";
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
  if (visualType.value !== props.character?.visual_type) payload.visual_type = visualType.value;
  
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
        <span>视觉类型</span>
        <select v-model="visualType">
          <option v-for="opt in VISUAL_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }} - {{ opt.caption }}
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
