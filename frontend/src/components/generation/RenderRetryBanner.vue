<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  errorCode?: string | null;
  errorMsg?: string | null;
  shotStatus?: string | null;
}>();

const shouldShow = computed(() => !!props.errorMsg || props.shotStatus === "failed");
</script>

<template>
  <div v-if="shouldShow" class="retry-banner">
    <strong>最近一次生成失败</strong>
    <p>{{ errorMsg || "请检查提示词与参考图后重试。" }}</p>
    <small v-if="errorCode">错误码：{{ errorCode }}</small>
  </div>
</template>

<style scoped>
.retry-banner {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(255, 99, 99, 0.4);
  background: rgba(255, 99, 99, 0.08);
}
.retry-banner strong {
  display: block;
  margin-bottom: 6px;
  color: #ffb3b3;
}
.retry-banner p,
.retry-banner small {
  margin: 0;
  color: var(--text-muted);
}
.retry-banner small {
  display: block;
  margin-top: 8px;
}
</style>
