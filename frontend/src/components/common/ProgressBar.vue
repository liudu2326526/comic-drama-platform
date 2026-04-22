<!-- frontend/src/components/common/ProgressBar.vue -->
<script setup lang="ts">
defineProps<{ value?: number; indeterminate?: boolean }>();
</script>
<template>
  <div class="pbar">
    <div v-if="indeterminate" class="pbar-indet" />
    <div v-else class="pbar-fill" :style="{ width: `${Math.min(100, Math.max(0, value ?? 0))}%` }" />
  </div>
</template>
<style scoped>
.pbar {
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}
.pbar-fill {
  height: 100%;
  background: var(--accent);
  transition: width 240ms ease;
}
.pbar-indet {
  height: 100%;
  width: 35%;
  background: var(--accent);
  animation: pbar-slide 1.2s ease-in-out infinite;
}
@keyframes pbar-slide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(300%);
  }
}
</style>
