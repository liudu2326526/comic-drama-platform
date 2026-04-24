<script setup lang="ts">
import type { RenderSubmitReference } from "@/types/api";

defineProps<{
  open: boolean;
  items: RenderSubmitReference[];
}>();

const emit = defineEmits<{
  select: [item: RenderSubmitReference];
}>();
</script>

<template>
  <div v-if="open && items.length" class="mention-menu" data-testid="reference-mention-menu">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="mention-option"
      @mousedown.prevent="emit('select', item)"
    >
      <img :src="item.image_url" :alt="item.alias ?? item.name" />
      <span>@{{ item.alias ?? item.name }}</span>
    </button>
  </div>
</template>

<style scoped>
.mention-menu {
  display: grid;
  gap: 4px;
  width: min(320px, 100%);
  margin-top: 6px;
  padding: 6px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  background: var(--panel-bg);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
}
.mention-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
}
.mention-option:hover {
  background: rgba(255, 255, 255, 0.06);
}
.mention-option img {
  width: 30px;
  height: 30px;
  border-radius: 4px;
  object-fit: cover;
}
.mention-option span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
