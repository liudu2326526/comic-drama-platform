<!-- frontend/src/components/common/StatusPill.vue -->
<script setup lang="ts">
defineProps<{ tone?: "success" | "warning" | "danger" | "info"; text: string }>();
</script>
<template>
  <span :class="['status-pill', `tone-${tone ?? 'info'}`]">
    <span class="dot" /> {{ text }}
  </span>
</template>
<style scoped>
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-muted);
}
.status-pill .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.tone-success {
  color: var(--success);
}
.tone-warning {
  color: var(--warning);
}
.tone-danger {
  color: var(--danger);
}
.tone-info {
  color: var(--accent);
}
</style>
