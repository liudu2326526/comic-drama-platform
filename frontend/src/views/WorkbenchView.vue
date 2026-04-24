<!-- frontend/src/views/WorkbenchView.vue -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import AppTopbar from "@/components/layout/AppTopbar.vue";
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
let sectionObserver: IntersectionObserver | null = null;

async function loadCurrent() {
  try {
    await store.load(String(route.params.id));
    // I2: 刷新页面时找回正在运行的任务
    await store.findAndTrackActiveJobs();
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

function observeWorkflowSections() {
  sectionObserver?.disconnect();
  if (!current.value || typeof IntersectionObserver === "undefined") return;

  sectionObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      const step = visible?.target.id.replace("panel-", "") as WorkflowStep | undefined;
      if (step && STEP_KEYS.includes(step) && step !== activeStep.value) {
        store.setStep(step);
      }
    },
    { root: null, rootMargin: "-18% 0px -62% 0px", threshold: [0.1, 0.35, 0.6] }
  );

  STEP_KEYS.forEach((step) => {
    const el = document.getElementById(`panel-${step}`);
    if (el) sectionObserver?.observe(el);
  });
}

onMounted(async () => {
  await loadCurrent();
  const step = route.query.step;
  if (typeof step === "string" && STEP_KEYS.includes(step as WorkflowStep)) {
    await changeStep(step as WorkflowStep);
  }
  await nextTick();
  observeWorkflowSections();
});

onBeforeUnmount(() => {
  sectionObserver?.disconnect();
});

watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) loadCurrent();
  }
);

watch(current, async () => {
  await nextTick();
  observeWorkflowSections();
});
</script>

<template>
  <div class="page-shell">
    <AppTopbar :title="current?.name ?? '加载中...'" :subtitle="subtitle">
      <button class="ghost-btn" :disabled="!current" @click="rollbackOpen = true">回退阶段</button>
      <button class="ghost-btn" @click="$router.push({ name: 'project-list' })">返回列表</button>
    </AppTopbar>

    <main class="workspace-layout">
      <WorkflowStepNav class="workflow-sidebar" :active="activeStep" @change="changeStep" />
      <section class="content-area">
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
