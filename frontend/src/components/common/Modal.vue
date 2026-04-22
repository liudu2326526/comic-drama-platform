<!-- frontend/src/components/common/Modal.vue -->
<script setup lang="ts">
defineProps<{ open: boolean; title?: string; danger?: boolean }>();
defineEmits<{ (e: "close"): void }>();
</script>
<template>
  <div v-if="open" class="modal-scrim" @click.self="$emit('close')">
    <div class="modal-card">
      <header class="modal-head">
        <h3 :class="{ danger }">{{ title }}</h3>
        <button @click="$emit('close')">×</button>
      </header>
      <div class="modal-body"><slot /></div>
      <footer class="modal-foot"><slot name="footer" /></footer>
    </div>
  </div>
</template>
<style scoped>
.modal-scrim {
  position: fixed;
  inset: 0;
  background: rgba(5, 6, 13, 0.72);
  display: grid;
  place-items: center;
  z-index: 800;
}
.modal-card {
  min-width: 420px;
  max-width: 560px;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-lg);
  padding: 24px;
  color: var(--text-primary);
  backdrop-filter: blur(14px);
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.modal-head h3 {
  margin: 0;
}
.modal-head h3.danger {
  color: var(--danger);
}
.modal-head button {
  background: transparent;
  border: none;
  color: var(--text-faint);
  font-size: 20px;
  cursor: pointer;
}
.modal-body {
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.6;
}
.modal-foot {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 18px;
}
</style>
