<!-- frontend/src/components/layout/AppTopbar.vue -->
<script setup lang="ts">
defineProps<{ title?: string; subtitle?: string }>();
</script>
<template>
  <header class="topbar">
    <div>
      <p class="eyebrow">Comic Drama Platform</p>
      <h1>{{ title ?? "漫剧生成工作台" }}</h1>
      <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
    </div>
    <div class="topbar-actions"><slot /></div>
  </header>
</template>
