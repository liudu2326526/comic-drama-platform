<!-- frontend/src/components/common/Toast.vue -->
<script setup lang="ts">
import { useToast } from "@/composables/useToast";
const toast = useToast();
</script>
<template>
  <TransitionGroup name="toast" tag="div" class="toast-stack">
    <div v-for="t in toast.items" :key="t.id" :class="['toast', `toast-${t.variant}`]">
      <div class="toast-body">
        <p class="toast-msg">{{ t.message }}</p>
        <p v-if="t.detail" class="toast-detail">{{ t.detail }}</p>
      </div>
      <button v-if="t.action" class="toast-action" @click="t.action!.onClick">
        {{ t.action.label }}
      </button>
      <button class="toast-close" @click="toast.dismiss(t.id)">×</button>
    </div>
  </TransitionGroup>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  top: 24px;
  right: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 900;
  max-width: 360px;
}

/* Toast Animation */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.toast-leave-to {
  opacity: 0;
  transform: scale(0.9);
}
.toast-move {
  transition: transform 0.3s ease;
}

.toast {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  backdrop-filter: blur(14px);
}
.toast-success {
  border-color: var(--success);
}
.toast-error {
  border-color: var(--danger);
}
.toast-warning {
  border-color: var(--warning);
}
.toast-msg {
  margin: 0;
  font-size: 14px;
}
.toast-detail {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}
.toast-action {
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.toast-close {
  background: transparent;
  border: none;
  color: var(--text-faint);
  cursor: pointer;
  font-size: 18px;
}
</style>
