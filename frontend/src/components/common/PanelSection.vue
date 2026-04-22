<!-- frontend/src/components/common/PanelSection.vue -->
<script setup lang="ts">
defineProps<{
  kicker: string;
  title: string;
}>();
</script>

<template>
  <section class="panel-section">
    <header class="panel-head">
      <div>
        <p class="panel-kicker">{{ kicker }}</p>
        <h2>{{ title }}</h2>
      </div>
      <div class="panel-actions">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>
