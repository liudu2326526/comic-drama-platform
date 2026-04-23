<!-- frontend/src/components/scene/SceneAssetsPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import SceneEditorModal from "./SceneEditorModal.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";
import type { SceneAsset } from "@/types";
import type { JobState, SceneUpdate } from "@/types/api";

const store = useWorkbenchStore();
const {
  current,
  selectedScene,
  selectedSceneId,
  activeGenerateScenesJobId,
  generateScenesError,
} = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const editorOpen = ref(false);
const rollbackOpen = ref(false);
const busy = ref(false);
const starting = ref(false);

// ---- 主 job 轮询 ----
const { job: generateJob } = useJobPolling(activeGenerateScenesJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markGenerateScenesSucceeded();
      toast.success("场景已生成");
    } catch (e) {
      store.markGenerateScenesFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "生成失败");
    store.markGenerateScenesFailed(msg);
    toast.error(msg);
  }
});

const generateProgressLabel = computed(() => {
  const j = generateJob.value;
  if (!j) return "正在排队…";
  if (j.total && j.total > 0) return `正在生成场景… ${j.done}/${j.total}`;
  return `正在生成场景… ${j.progress}%`;
});

// ---- 单项 regen 轮询(按当前选中项精确找回) ----
const activeSceneRegenJobId = computed(() => {
  if (!selectedSceneId.value) return null;
  return store.regenJobIdFor("scene", selectedSceneId.value);
});
const regenProgressByJobId = ref<Record<string, number>>({});

useJobPolling(activeSceneRegenJobId, {
  onProgress: (job: JobState) => {
    regenProgressByJobId.value[job.id] = job.progress;
  },
  onSuccess: async () => {
    if (selectedSceneId.value) {
      store.markRegenByKeySucceeded(`scene:${selectedSceneId.value}`);
    }
    await store.reload();
    toast.success("场景参考图已重生成");
  },
  onError: (j, err) => {
    if (selectedSceneId.value) {
      store.markRegenByKeyFailed(`scene:${selectedSceneId.value}`);
    }
    toast.error(j?.error_msg ?? (err instanceof ApiError ? messageFor(err.code, err.message) : "重生成失败"));
  }
});

// ---- 动作 ----
async function handleGenerate() {
  if (!flags.value.canGenerateScenes) {
    toast.warning("当前阶段不允许生成场景", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  starting.value = true;
  try {
    await store.generateScenes({});
  } catch (e) {
    const msg = e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败";
    store.markGenerateScenesFailed(msg);
    toast.error(msg);
  } finally {
    starting.value = false;
  }
}

function openEdit() {
  if (!flags.value.canEditScenes) {
    toast.warning("当前阶段不允许编辑场景,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  editorOpen.value = true;
}

async function handleEditSubmit(payload: SceneUpdate) {
  if (!selectedScene.value) return;
  busy.value = true;
  try {
    await store.patchScene(selectedScene.value.id, payload);
    toast.success("场景已保存");
    editorOpen.value = false;
  } catch (e) {
    if (e instanceof ApiError && e.code === 40301) {
      toast.warning("当前阶段不允许编辑场景,如需修改请回退阶段", {
        action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
      });
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("保存失败");
    }
  } finally {
    busy.value = false;
  }
}

async function handleRegen() {
  if (!selectedScene.value) return;
  if (!flags.value.canEditScenes) {
    toast.warning("当前阶段不允许编辑场景,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  busy.value = true;
  try {
    await store.regenerateScene(selectedScene.value.id);
    toast.info("已触发重生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  } finally {
    busy.value = false;
  }
}

async function handleConfirmStage() {
  if (!flags.value.canConfirmScenes) {
    toast.warning("当前阶段不允许进入镜头生成");
    return;
  }
  busy.value = true;
  try {
    await store.confirmScenesStage();
    toast.success("已进入镜头生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "确认失败");
  } finally {
    busy.value = false;
  }
}

// ---- UI helpers ----
const canStartGenerate = computed(
  () =>
    flags.value.canGenerateScenes &&
    (current.value?.scenes.length ?? 0) === 0 &&
    !activeGenerateScenesJobId.value
);
const THEME_CLASS: Record<string, string> = {
  palace: "theme-palace",
  academy: "theme-academy",
  harbor: "theme-harbor"
};
const themeClass = (s: SceneAsset) => (s.theme ? THEME_CLASS[s.theme] ?? "" : "");

const selectedRegenJobId = computed(() =>
  selectedScene.value
    ? store.regenJobIdFor("scene", selectedScene.value.id)
    : null
);
const selectedHasRegenJob = computed(() => !!selectedRegenJobId.value);
const selectedRegenProgress = computed(() =>
  selectedRegenJobId.value ? regenProgressByJobId.value[selectedRegenJobId.value] ?? 0 : 0
);
</script>

<template>
  <PanelSection v-if="current" kicker="04" title="场景设定">
    <template #actions>
      <button
        class="primary-btn"
        type="button"
        :disabled="busy || !flags.canConfirmScenes"
        @click="handleConfirmStage"
      >
        确认进入镜头生成
      </button>
    </template>

    <div v-if="activeGenerateScenesJobId" class="gen-banner running">
      <div class="gen-head">
        <strong>{{ generateProgressLabel }}</strong>
      </div>
      <ProgressBar :value="generateJob?.progress ?? 0" />
    </div>

    <div v-else-if="generateScenesError" class="gen-banner error">
      <div class="gen-head">
        <strong>场景生成失败</strong>
        <button class="ghost-btn small" @click="handleGenerate">重试</button>
      </div>
      <p>{{ generateScenesError }}</p>
    </div>

    <div v-else-if="canStartGenerate" class="empty-cta">
      <p>尚未生成场景 · 角色设定确认后可触发 AI 匹配项目中需要的场景</p>
      <button class="primary-btn large" :disabled="starting" @click="handleGenerate">
        {{ starting ? "启动中..." : "生成场景资产" }}
      </button>
    </div>
    <div v-else-if="!current.scenes.length" class="empty-note">
      尚未生成场景 · 进入场景设定后可触发 AI 生成
    </div>

    <div v-if="current.scenes.length" class="asset-browser">
      <div class="asset-list-panel">
        <div class="list-head">
          <strong>所有场景</strong>
          <span>{{ current.scenes.length }} 个资产</span>
        </div>
        <div class="asset-list">
          <button
            v-for="scene in current.scenes"
            :key="scene.id"
            class="asset-list-item"
            :class="{ active: selectedSceneId === scene.id }"
            type="button"
            @click="store.selectScene(scene.id)"
          >
            <div class="list-item-head">
              <strong>{{ scene.name }}</strong>
            </div>
            <small>{{ scene.summary ?? "" }}</small>
          </button>
        </div>
      </div>

      <div v-if="selectedScene" class="asset-detail-panel">
        <div class="subpage-head">
          <div>
            <p class="panel-kicker">场景详情</p>
            <h3>{{ selectedScene.name }}</h3>
          </div>
          <span class="tag">{{ selectedScene.usage }}</span>
        </div>

        <div class="asset-layout">
          <div class="reference-stage scene-stage" :class="themeClass(selectedScene)">
            <div class="reference-badge">场景参考图</div>
            <img
              v-if="selectedScene.reference_image_url"
              :src="selectedScene.reference_image_url"
              :alt="selectedScene.name"
              loading="lazy"
              class="ref-image"
            />
            <div v-else class="scene-layers">
              <span class="moon" />
              <span class="wall" />
              <span class="well" />
            </div>
          </div>

          <div class="asset-info">
            <article class="asset-copy">
              <label>场景描述</label>
              <p>{{ selectedScene.description || "(尚无描述)" }}</p>
            </article>

            <article class="asset-meta">
              <span>视觉风格参考</span>
              <ul v-if="selectedScene.meta.length">
                <li v-for="meta in selectedScene.meta" :key="meta">{{ meta }}</li>
              </ul>
              <p v-else class="faint">暂无 meta</p>
            </article>

            <div class="asset-actions">
              <button
                class="ghost-btn"
                :disabled="busy || !flags.canEditScenes"
                :title="flags.canEditScenes ? '编辑描述' : '当前阶段不允许编辑场景,请回退阶段'"
                @click="openEdit"
              >
                编辑描述
              </button>
              <button
                class="ghost-btn"
                :disabled="busy || selectedHasRegenJob || !flags.canEditScenes"
                :title="flags.canEditScenes ? '重新生成参考图' : '当前阶段不允许编辑场景,请回退阶段'"
                @click="handleRegen"
              >
                {{ selectedHasRegenJob ? `重生成中…(${selectedRegenProgress}%)` : "重新生成参考图" }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <SceneEditorModal
      :open="editorOpen"
      :scene="selectedScene"
      :busy="busy"
      @close="editorOpen = false"
      @submit="handleEditSubmit"
    />

    <StageRollbackModal :open="rollbackOpen" @close="rollbackOpen = false" />
  </PanelSection>
</template>

<style scoped>
.gen-banner { margin-bottom: 16px; padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--panel-border); background: rgba(255,255,255,0.03); }
.gen-banner.error { border-color: var(--danger); }
.gen-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.empty-cta { text-align: center; padding: 32px 0 16px; }
.empty-cta p { color: var(--text-faint); margin-bottom: 16px; }
.list-item-head { display: flex; justify-content: space-between; align-items: center; }
.badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); color: var(--text-muted); }
.ref-image { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.asset-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.faint { color: var(--text-faint); font-size: 12px; }

.asset-browser { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 20px; }
.asset-list-panel { padding: 18px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: var(--radius-md); }
.list-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.list-head strong { font-size: 15px; }
.list-head span { font-size: 12px; color: var(--text-faint); }
.asset-list { display: flex; flex-direction: column; gap: 10px; }
.asset-list-item { width: 100%; padding: 14px; text-align: left; background: rgba(255,255,255,0.02); border: 1px solid var(--panel-border); border-radius: var(--radius-sm); cursor: pointer; transition: all 160ms; }
.asset-list-item:hover { background: rgba(255,255,255,0.05); }
.asset-list-item.active { background: var(--accent-dim); border-color: var(--accent); }
.asset-list-item strong { display: block; font-size: 14px; margin-bottom: 4px; }
.asset-list-item small { display: block; font-size: 12px; color: var(--text-muted); }
.asset-detail-panel { padding: 24px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: var(--radius-md); }
.subpage-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.subpage-head h3 { margin: 0; font-size: 22px; }
.asset-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 24px; }
.reference-stage { position: relative; min-height: 280px; border-radius: var(--radius-md); background: #0b0d1a; border: 1px solid var(--panel-border); overflow: hidden; }
.reference-badge { position: absolute; top: 12px; left: 12px; padding: 4px 8px; background: rgba(0,0,0,0.5); color: #fff; font-size: 10px; border-radius: 4px; z-index: 1; }
.scene-layers { position: absolute; inset: 0; }
.moon { position: absolute; top: 40px; right: 40px; width: 60px; height: 60px; background: radial-gradient(circle, #fff, transparent); border-radius: 50%; opacity: 0.8; }
.wall { position: absolute; bottom: 40px; left: 20px; right: 20px; height: 100px; background: rgba(255, 255, 255, 0.1); border-radius: 12px; }
.well { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); width: 80px; height: 40px; background: rgba(255, 255, 255, 0.05); border: 4px solid rgba(255, 255, 255, 0.1); border-radius: 40px 40px 0 0; }
.asset-info { display: flex; flex-direction: column; gap: 20px; }
.asset-copy label { display: block; font-size: 12px; color: var(--accent); margin-bottom: 8px; }
.asset-copy p { margin: 0; font-size: 14px; color: var(--text-muted); line-height: 1.6; }
.asset-meta span { display: block; font-size: 12px; color: var(--text-faint); margin-bottom: 10px; }
.asset-meta ul { margin: 0; padding-left: 18px; font-size: 13px; color: var(--text-muted); line-height: 1.6; }
.tag { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); padding: 4px 10px; border-radius: 999px; font-size: 12px; }
.empty-note { padding: 40px 0; text-align: center; color: var(--text-faint); font-size: 14px; }
</style>
