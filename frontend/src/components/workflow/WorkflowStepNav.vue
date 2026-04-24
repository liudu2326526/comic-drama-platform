<!-- frontend/src/components/workflow/WorkflowStepNav.vue -->
<script setup lang="ts">
import type { WorkflowStep } from "@/store/workbench";
const steps: { key: WorkflowStep; label: string }[] = [
  { key: "setup", label: "新建项目" },
  { key: "storyboard", label: "分镜工作台" },
  { key: "character", label: "角色设定" },
  { key: "scene", label: "场景设定" },
  { key: "render", label: "镜头生成" },
  { key: "export", label: "导出" }
];
defineProps<{ active: WorkflowStep }>();
defineEmits<{ (e: "change", step: WorkflowStep): void }>();
</script>
<template>
  <nav class="workflow-nav" aria-label="工作流阶段">
    <span class="workflow-nav-title">流程</span>
    <button
      v-for="s in steps"
      :key="s.key"
      :class="['workflow-chip', { active: active === s.key }]"
      type="button"
      @click="$emit('change', s.key)"
    >
      {{ s.label }}
    </button>
  </nav>
</template>
