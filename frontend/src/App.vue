<script setup lang="ts">
import { RouterView } from "vue-router";
import Toast from "@/components/common/Toast.vue";
import Modal from "@/components/common/Modal.vue";
import { useConfirmState, resolveConfirm } from "@/composables/useConfirm";

const state = useConfirmState();
</script>

<template>
  <RouterView />
  <Toast />
  <Modal :open="state.open" :title="state.title" :danger="state.danger" @close="resolveConfirm(false)">
    <p>{{ state.body }}</p>
    <template #footer>
      <button class="ghost-btn" @click="resolveConfirm(false)">{{ state.cancelText }}</button>
      <button :class="['primary-btn', { danger: state.danger }]" @click="resolveConfirm(true)">
        {{ state.confirmText }}
      </button>
    </template>
  </Modal>
</template>
