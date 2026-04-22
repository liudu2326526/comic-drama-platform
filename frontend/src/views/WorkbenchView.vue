<!-- frontend/src/views/WorkbenchView.vue -->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import SidebarProjects from "@/components/layout/SidebarProjects.vue";
import WorkflowStepNav from "@/components/workflow/WorkflowStepNav.vue";
import ProjectSetupPanel from "@/components/setup/ProjectSetupPanel.vue";
import StoryboardPanel from "@/components/storyboard/StoryboardPanel.vue";
import CharacterAssetsPanel from "@/components/character/CharacterAssetsPanel.vue";
import SceneAssetsPanel from "@/components/scene/SceneAssetsPanel.vue";
import GenerationPanel from "@/components/generation/GenerationPanel.vue";
import ExportPanel from "@/components/export/ExportPanel.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore, type WorkflowStep } from "@/store/workbench";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";

const route = useRoute();
const router = useRouter();
const store = useWorkbenchStore();
const { current, loading, activeStep } = storeToRefs(store);
const toast = useToast();

const rollbackOpen = ref(false);
const subtitle = computed(() => current.value?.stage ?? "加载中");
const STEP_KEYS: WorkflowStep[] = ["setup", "storyboard", "character", "scene", "render", "export"];

async function loadCurrent() {
  try {
    await store.load(String(route.params.id));
    // 若项目已过 draft 阶段,上一个 parse job 必然已结束,清掉 job id 避免空转轮询
    if (store.current?.stage_raw && store.current.stage_raw !== "draft") {
      store.markParseSucceeded();
    }
  } catch (e) {
    if (e instanceof ApiError && e.code === 40401) {
      toast.error("项目不存在");
      await router.replace({ name: "project-list" });
    } else {
      toast.error(e instanceof Error ? e.message : "加载失败");
    }
  }
}

async function changeStep(step: WorkflowStep) {
  store.setStep(step);
  await router.replace({ query: { ...route.query, step } });
  await nextTick();
  document.getElementById(`panel-${step}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

onMounted(async () => {
  await loadCurrent();
  const step = route.query.step;
  if (typeof step === "string" && STEP_KEYS.includes(step as WorkflowStep)) {
    await changeStep(step as WorkflowStep);
  }
});

watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) loadCurrent();
  }
);
</script>

<template>
  <div class="page-shell">
    <AppTopbar :title="current?.name ?? '加载中...'" :subtitle="subtitle">
      <button class="ghost-btn" :disabled="!current" @click="rollbackOpen = true">回退阶段</button>
      <button class="ghost-btn" @click="$router.push({ name: 'project-list' })">返回列表</button>
    </AppTopbar>

    <main class="workspace-layout">
      <SidebarProjects />
      <section class="content-area">
        <WorkflowStepNav :active="activeStep" @change="changeStep" />
        <div v-if="loading" class="skeleton">正在加载项目...</div>
        <template v-else-if="current">
          <div id="panel-setup"><ProjectSetupPanel /></div>
          <div id="panel-storyboard"><StoryboardPanel /></div>
          <div id="panel-character"><CharacterAssetsPanel /></div>
          <div id="panel-scene"><SceneAssetsPanel /></div>
          <div id="panel-render"><GenerationPanel /></div>
          <div id="panel-export"><ExportPanel /></div>
        </template>
      </section>
    </main>

    <StageRollbackModal
      v-if="current"
      :open="rollbackOpen"
      @close="rollbackOpen = false"
    />
  </div>
</template>

<style scoped>
.content-area {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.skeleton {
  padding: 60px 0;
  text-align: center;
  color: var(--text-faint);
  background: var(--panel-bg);
  border-radius: var(--radius-lg);
  border: 1px solid var(--panel-border);
}
</style>
