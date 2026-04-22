<!-- frontend/src/components/workflow/StageRollbackModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import Modal from "@/components/common/Modal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";
import type { ProjectStageRaw } from "@/types/api";

const STAGE_OPTIONS: { value: ProjectStageRaw; label: string }[] = [
  { value: "draft", label: "草稿中" },
  { value: "storyboard_ready", label: "分镜已生成" },
  { value: "characters_locked", label: "角色已锁定" },
  { value: "scenes_locked", label: "场景已匹配" },
  { value: "rendering", label: "镜头生成中" },
  { value: "ready_for_export", label: "待导出" },
  { value: "exported", label: "已导出" }
];

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: "close"): void }>();

const store = useWorkbenchStore();
const { current } = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const target = ref<ProjectStageRaw>("draft");
const loading = ref(false);
const stageLabel = (stage: ProjectStageRaw) =>
  STAGE_OPTIONS.find((o) => o.value === stage)?.label ?? stage;

const currentRaw = computed(() => current.value?.stage_raw ?? null);
const currentIdx = computed(() => STAGE_OPTIONS.findIndex((o) => o.value === currentRaw.value));
const options = computed(() =>
  STAGE_OPTIONS.filter((_, i) => currentIdx.value > 0 && i < currentIdx.value)
);

watch(
  () => props.open,
  (open) => {
    if (open) {
      target.value = options.value[options.value.length - 1]?.value ?? "draft";
    }
  }
);

async function confirm() {
  if (!flags.value.canRollback) {
    toast.warning("当前阶段不允许回退");
    return;
  }
  loading.value = true;
  try {
    const resp = await store.rollback({ to_stage: target.value });
    const inv = resp.invalidated;
    toast.success(`已从「${stageLabel(resp.from_stage)}」回退到「${stageLabel(resp.to_stage)}」`, {
      detail: `重置镜头 ${inv.shots_reset} 个, 解锁角色 ${inv.characters_unlocked} 个, 解锁场景 ${inv.scenes_unlocked} 个`
    });
    emit("close");
  } catch (e) {
    if (e instanceof ApiError) toast.error(messageFor(e.code, e.message));
    else toast.error("回退失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Modal :open="open" title="回退阶段" danger @close="emit('close')">
    <p>当前阶段: <b>{{ current?.stage ?? "-" }}</b></p>
    <p v-if="!flags.canRollback" class="warn">当前阶段不支持回退。</p>
    <template v-else>
      <p>选择目标阶段, 该阶段之后的资产将被失效并需要重做。</p>
      <select v-model="target" class="select">
        <option v-for="o in options" :key="o.value" :value="o.value">
          {{ o.label }}
        </option>
      </select>
    </template>
    <template #footer>
      <button class="ghost-btn" @click="emit('close')">取消</button>
      <button
        class="primary-btn danger"
        :disabled="!flags.canRollback || loading"
        @click="confirm"
      >
        {{ loading ? "执行中..." : "我已了解, 执行回退" }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.select {
  width: 100%;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  margin-top: 12px;
}
.warn {
  color: var(--warning);
}
.primary-btn.danger {
  background: var(--danger);
  color: #fff;
}
b {
  color: var(--accent);
}
</style>
