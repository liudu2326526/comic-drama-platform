<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import RenderVersionHistory from "@/components/generation/RenderVersionHistory.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";
import type {
  RenderSubmitReference,
  ShotVideoDurationPreset,
  ShotVideoModelType,
  ShotVideoResolution,
  ShotVideoVersionRead,
} from "@/types/api";

const store = useWorkbenchStore();
const {
  current,
  selectedShotId,
  renderShots,
  activeDraftJobId,
  activeDraftShotId,
  activeRenderJobId,
  activeRenderShotId,
  renderHistoryLoadingShotId,
} = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const historyOpen = ref(false);
const submitting = ref(false);
const loadingDraft = ref(false);
const draftPrompt = ref("");
const draftReferences = ref<RenderSubmitReference[]>([]);

const selectedRenderShot = computed(
  () => renderShots.value.find((item) => item.shotId === selectedShotId.value) ?? renderShots.value[0] ?? null
);
const selectedDraft = computed(() =>
  selectedRenderShot.value ? store.renderDraftFor(selectedRenderShot.value.shotId) : null
);
const selectedVideoOptions = computed(() =>
  selectedRenderShot.value ? store.videoDraftOptionsFor(selectedRenderShot.value.shotId) : null
);
const selectedVersions = computed<ShotVideoVersionRead[]>(() =>
  selectedRenderShot.value ? store.videoVersionsFor(selectedRenderShot.value.shotId) : []
);
const currentVideoVersion = computed(
  () => selectedVersions.value.find((item) => item.is_current) ?? selectedVersions.value[0] ?? null
);
const currentParams = computed(() => {
  if (currentVideoVersion.value?.params_snapshot) {
    return toVideoParamSummary(currentVideoVersion.value.params_snapshot);
  }
  return selectedRenderShot.value ? store.videoDraftOptionsFor(selectedRenderShot.value.shotId) : null;
});
const previewVideoUrl = computed(
  () => currentVideoVersion.value?.video_url ?? selectedRenderShot.value?.videoUrl ?? null
);
const showVideoGeneratingBanner = computed(() =>
  Boolean(
    previewVideoUrl.value &&
    activeRenderJobId.value &&
    activeRenderShotId.value === selectedRenderShot.value?.shotId
  )
);
const renderProgress = computed(() => {
  if (activeRenderShotId.value !== selectedRenderShot.value?.shotId) return 0;
  return selectedRenderShot.value?.progress ?? 0;
});
const generateVideoDisabled = computed(() => {
  if (!selectedRenderShot.value || !selectedDraft.value || !flags.value.canRender) return true;
  const isActiveShot = !!activeRenderJobId.value && activeRenderShotId.value === selectedRenderShot.value.shotId;
  return isActiveShot || !selectedDraft.value.prompt.trim() || selectedDraft.value.references.length === 0;
});
const generateVideoButtonText = computed(() => {
  if (submitting.value || (activeRenderJobId.value && activeRenderShotId.value === selectedRenderShot.value?.shotId)) {
    return "视频生成中...";
  }
  return currentVideoVersion.value?.video_url ? "重新生成视频" : "生成视频";
});
const generateDraftDisabled = computed(() =>
  !flags.value.canRender || loadingDraft.value || Boolean(activeDraftJobId.value)
);
const generateDraftButtonText = computed(() =>
  loadingDraft.value || activeDraftJobId.value ? "草稿生成中..." : "生成草稿"
);
const hasEnteredRenderPhase = computed(() =>
  ["scenes_locked", "rendering", "ready_for_export", "exported"].includes(current.value?.stage_raw ?? "")
);
const renderBlockedMessage = computed(() => {
  const stage = current.value?.stage_raw;
  if (stage === "draft") return "请先完成小说解析与分镜生成后再进入镜头生成。";
  if (stage === "storyboard_ready") return "请先完成角色设定，并确认进入场景设定。";
  if (stage === "characters_locked") return "请先完成场景设定，并确认进入镜头生成。";
  return "当前阶段暂不可生成镜头草稿。";
});

function toVideoParamSummary(snapshot: Record<string, unknown>) {
  return {
    duration: snapshot.duration == null ? null : Number(snapshot.duration),
    resolution: String(snapshot.resolution ?? "480p") as ShotVideoResolution,
    modelType: String(snapshot.model_type ?? "fast") as ShotVideoModelType,
  };
}

function syncDraftFromStore() {
  const shotId = selectedRenderShot.value?.shotId;
  if (!shotId) {
    draftPrompt.value = "";
    draftReferences.value = [];
    return;
  }
  const draft = store.renderDraftFor(shotId);
  draftPrompt.value = draft?.prompt ?? "";
  draftReferences.value = (draft?.references ?? []).map((item) => ({
    id: item.id,
    kind: item.kind,
    source_id: item.source_id,
    name: item.name,
    image_url: item.image_url,
  }));
}

watch(
  () => selectedRenderShot.value?.shotId,
  async (shotId) => {
    syncDraftFromStore();
    if (!shotId) return;
    if (!store.renderDraftFor(shotId)) {
      try {
        const draft = await store.fetchRenderDraft(shotId);
        draftPrompt.value = draft.prompt;
        draftReferences.value = draft.references.map((item) => ({
          id: item.id,
          kind: item.kind,
          source_id: item.source_id,
          name: item.name,
          image_url: item.image_url,
        }));
      } catch {
        // noop
      }
    }
    if (!store.videoVersionsFor(shotId).length) {
      try {
        await store.fetchVideoVersions(shotId);
      } catch {
        // noop
      }
    }
  },
  { immediate: true }
);

useJobPolling(activeDraftJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    const shotId = activeDraftShotId.value;
    if (!shotId) {
      return;
    }
    try {
      const draft = await store.fetchRenderDraft(shotId);
      draftPrompt.value = draft.prompt;
      draftReferences.value = draft.references.map((item) => ({
        id: item.id,
        kind: item.kind,
        source_id: item.source_id,
        name: item.name,
        image_url: item.image_url,
      }));
      store.markDraftSucceeded(shotId);
      toast.success("草稿生成完成");
    } catch (e) {
      const msg = e instanceof ApiError ? messageFor(e.code, e.message) : "加载已保存草稿失败";
      store.markDraftFailed(shotId, msg);
      toast.error(msg);
    }
  },
  onError: (j, err) => {
    const shotId = activeDraftShotId.value;
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "生成草稿失败");
    if (shotId) store.markDraftFailed(shotId, msg);
    toast.error(msg);
  }
});

useJobPolling(activeRenderJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      const shotId = activeRenderShotId.value;
      await store.reload();
      store.markRenderSucceeded();
      if (shotId) await store.fetchVideoVersions(shotId);
      toast.success("视频生成完成");
    } catch (e) {
      store.markRenderFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "视频生成失败");
    store.markRenderFailed(msg);
    toast.error(msg);
  }
});

function selectShot(shotId: string) {
  store.selectShot(shotId);
}

function onPromptInput(value: string) {
  if (!selectedRenderShot.value) return;
  draftPrompt.value = value;
  store.updateRenderDraft(selectedRenderShot.value.shotId, { prompt: value });
}

function removeReference(id: string) {
  if (!selectedRenderShot.value) return;
  draftReferences.value = draftReferences.value.filter((item) => item.id !== id);
  store.updateRenderDraft(selectedRenderShot.value.shotId, { references: draftReferences.value as never });
}

async function generateDraft() {
  if (!selectedRenderShot.value || !flags.value.canRender) return;
  loadingDraft.value = true;
  try {
    await store.generateRenderDraft(selectedRenderShot.value.shotId);
    toast.info("已提交草稿生成任务");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "生成草稿失败");
  } finally {
    loadingDraft.value = false;
  }
}

async function generateVideo() {
  if (!selectedRenderShot.value || generateVideoDisabled.value) return;
  submitting.value = true;
  try {
    store.updateRenderDraft(selectedRenderShot.value.shotId, {
      prompt: draftPrompt.value,
      references: draftReferences.value as never,
    });
    await store.generateVideoFromDraft(selectedRenderShot.value.shotId);
    toast.info("已提交视频生成任务");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "视频生成失败");
  } finally {
    submitting.value = false;
  }
}

function setDuration(duration: ShotVideoDurationPreset) {
  if (!selectedRenderShot.value) return;
  store.setVideoDraftOptions(selectedRenderShot.value.shotId, {
    duration: selectedVideoOptions.value?.duration === duration ? null : duration
  });
}

function setResolution(resolution: ShotVideoResolution) {
  if (!selectedRenderShot.value) return;
  store.setVideoDraftOptions(selectedRenderShot.value.shotId, { resolution });
}

function setModelType(modelType: ShotVideoModelType) {
  if (!selectedRenderShot.value) return;
  store.setVideoDraftOptions(selectedRenderShot.value.shotId, { modelType });
}

async function handleSelectVersion(videoId: string) {
  if (!selectedRenderShot.value) return;
  try {
    await store.selectVideoVersion(selectedRenderShot.value.shotId, videoId);
    historyOpen.value = false;
    toast.success("已切换当前版本");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "切换版本失败");
  }
}

async function handleLockShot() {
  if (!selectedRenderShot.value || !flags.value.canLockShot || !selectedRenderShot.value.currentVideoRenderId) return;
  try {
    await store.lockShot(selectedRenderShot.value.shotId);
    toast.success("镜头已锁定为最终版");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "锁定最终版失败");
  }
}
</script>

<template>
  <PanelSection v-if="current" kicker="05" title="镜头生成">
    <template #actions>
      <span v-if="current.generationProgress" class="tag success">{{ current.generationProgress }}</span>
      <button class="primary-btn" type="button" disabled>批量继续生成</button>
    </template>

    <div v-if="!hasEnteredRenderPhase" class="empty-note">
      {{ renderBlockedMessage }}
    </div>
    <div v-else-if="!renderShots.length" class="empty-note">
      尚未发现可渲染镜头
    </div>
    <div v-else class="generation-layout">
      <div class="generation-sidebar">
        <div class="sidebar-head">
          <strong>镜头列表</strong>
          <span>{{ renderShots.length }} 个镜头</span>
        </div>
        <div class="shot-list">
          <button
            v-for="item in renderShots"
            :key="item.shotId"
            class="shot-card"
            :class="{ active: item.shotId === selectedRenderShot?.shotId }"
            type="button"
            @click="selectShot(item.shotId)"
          >
            <div class="shot-card-head">
              <strong>{{ item.title }}</strong>
              <span class="shot-status" :class="item.status">
                {{
                  item.status === "success"
                    ? "已完成"
                    : item.status === "processing"
                      ? "待处理"
                      : "待处理"
                }}
              </span>
            </div>
            <p>{{ item.summary }}</p>
            <small v-if="item.versionNo">当前版本 v{{ item.versionNo }}</small>
          </button>
        </div>
      </div>

      <div v-if="selectedRenderShot" class="generation-main">
        <div class="draft-panel">
          <div class="panel-headline">
            <div>
              <p class="panel-kicker">Render Draft</p>
              <h3>{{ selectedRenderShot.title }}</h3>
            </div>
            <div class="draft-actions">
              <button
                class="ghost-btn"
                type="button"
                data-testid="generate-draft-btn"
                :disabled="generateDraftDisabled"
                @click="generateDraft"
              >
                {{ generateDraftButtonText }}
              </button>
              <button
                class="ghost-btn"
                type="button"
                data-testid="history-btn"
                :disabled="!selectedRenderShot || renderHistoryLoadingShotId === selectedRenderShot.shotId"
                @click="historyOpen = true"
              >
                查看历史版本
              </button>
              <button
                class="primary-btn"
                type="button"
                data-testid="generate-video-btn"
                :disabled="generateVideoDisabled"
                @click="generateVideo"
              >
                {{ generateVideoButtonText }}
              </button>
            </div>
          </div>

          <div class="selectors">
            <article>
              <span>视频时长</span>
              <div class="selector-row">
                <button data-testid="duration-option" class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.duration === 4 }" @click="setDuration(4)">4 秒</button>
                <button data-testid="duration-option" class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.duration === 5 }" @click="setDuration(5)">5 秒</button>
                <button data-testid="duration-option" class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.duration === 8 }" @click="setDuration(8)">8 秒</button>
                <button data-testid="duration-option" class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.duration === 10 }" @click="setDuration(10)">10 秒</button>
              </div>
            </article>
            <article>
              <span>分辨率</span>
              <div class="selector-row">
                <button data-testid="resolution-480p" class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.resolution === '480p' }" @click="setResolution('480p')">480P</button>
                <button class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.resolution === '720p' }" @click="setResolution('720p')">720P</button>
              </div>
            </article>
            <article>
              <span>模型类型</span>
              <div class="selector-row">
                <button class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.modelType === 'standard' }" @click="setModelType('standard')">标准</button>
                <button class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.modelType === 'fast' }" @click="setModelType('fast')">极速</button>
              </div>
            </article>
          </div>

          <div v-if="activeRenderJobId && activeRenderShotId === selectedRenderShot.shotId" class="render-progress">
            <div class="progress-head">
              <strong>镜头生成中</strong>
              <span>{{ renderProgress }}%</span>
            </div>
            <ProgressBar :value="renderProgress" />
          </div>

          <label class="field-label" for="draft-prompt">镜头提示词</label>
          <textarea
            id="draft-prompt"
            data-testid="draft-prompt"
            :value="draftPrompt"
            class="prompt-input"
            rows="8"
            placeholder="先生成草稿，再按需要调整镜头提示词"
            @input="onPromptInput(($event.target as HTMLTextAreaElement).value)"
          />

          <div class="reference-head">
            <strong>参考图</strong>
            <span>{{ draftReferences.length }} 张</span>
          </div>
          <div v-if="draftReferences.length" class="reference-grid">
            <article v-for="item in draftReferences" :key="item.id" class="reference-card">
              <img :src="item.image_url" :alt="item.name" />
              <div class="reference-copy">
                <strong>{{ item.name }}</strong>
                <small>{{ item.kind }}</small>
              </div>
              <button class="ghost-btn small" type="button" @click="removeReference(item.id)">删除</button>
            </article>
          </div>
          <div v-else class="empty-inline">至少保留 1 张参考图后才能生成视频。</div>
        </div>

        <div class="preview-panel">
          <div class="preview-frame">
            <div class="frame-caption">
              <span>Video Preview</span>
              <strong>{{ selectedRenderShot.title }}</strong>
            </div>
            <video
              v-if="previewVideoUrl"
              class="preview-video"
              :src="previewVideoUrl"
              controls
              playsinline
              preload="metadata"
            />
            <div v-else-if="activeRenderJobId && activeRenderShotId === selectedRenderShot.shotId" class="preview-empty">
              正在生成成品视频，请稍候
            </div>
            <div v-else class="preview-empty">
              当前还没有可播放的成品视频
            </div>
          </div>

          <div v-if="showVideoGeneratingBanner" class="info-banner">
            <strong>新版本生成中</strong>
            <p>继续展示当前成功版本，新的成品视频完成后会自动刷新。</p>
          </div>

          <div class="preview-notes">
            <article v-if="currentParams">
              <span>当前参数</span>
              <dl class="param-summary">
                <div><dt>时长</dt><dd>{{ currentParams.duration == null ? "未指定" : `${currentParams.duration} 秒` }}</dd></div>
                <div><dt>分辨率</dt><dd>{{ currentParams.resolution }}</dd></div>
                <div><dt>模型</dt><dd>{{ currentParams.modelType === "fast" ? "极速" : "标准" }}</dd></div>
              </dl>
            </article>
            <article>
              <span>操作</span>
              <button
                class="primary-btn"
                type="button"
                :disabled="!flags.canLockShot || !selectedRenderShot.currentVideoRenderId"
                @click="handleLockShot"
              >
                锁定最终版
              </button>
            </article>
          </div>
        </div>
      </div>
    </div>

    <RenderVersionHistory
      :open="historyOpen"
      :versions="selectedVersions"
      :current-render-id="selectedRenderShot?.currentVideoRenderId ?? null"
      :loading="renderHistoryLoadingShotId === selectedRenderShot?.shotId"
      @close="historyOpen = false"
      @select="handleSelectVersion"
    />
  </PanelSection>
</template>

<style scoped>
.generation-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 20px;
}
.generation-sidebar,
.draft-panel,
.preview-panel {
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.generation-main {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 20px;
}
.sidebar-head,
.panel-headline,
.reference-head,
.progress-head,
.frame-caption {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.sidebar-head span,
.reference-head span,
.frame-caption span {
  font-size: 12px;
  color: var(--text-faint);
}
.shot-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}
.shot-card {
  width: 100%;
  padding: 14px;
  text-align: left;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.shot-card.active {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.shot-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.shot-card p,
.shot-card small {
  margin: 6px 0 0;
  color: var(--text-muted);
}
.shot-status {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}
.shot-status.success {
  color: var(--success);
}
.shot-status.processing {
  color: var(--warning);
}
.shot-status.failed,
.shot-status.warning {
  color: var(--danger);
}
.draft-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.selectors {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}
.selectors article span {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--accent);
}
.selector-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.selector-row .ghost-btn.active {
  border-color: var(--accent);
  color: var(--accent);
}
.field-label {
  display: block;
  margin: 18px 0 8px;
  font-size: 12px;
  color: var(--accent);
}
.prompt-input {
  width: 100%;
  min-height: 180px;
  padding: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  resize: vertical;
}
.reference-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.reference-card {
  overflow: hidden;
  border-radius: var(--radius-sm);
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.02);
}
.reference-card img {
  display: block;
  width: 100%;
  height: 132px;
  object-fit: cover;
}
.reference-copy {
  padding: 12px 12px 0;
}
.reference-copy strong {
  display: block;
}
.reference-copy small {
  color: var(--text-faint);
}
.reference-card .ghost-btn {
  margin: 12px;
}
.preview-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.preview-frame {
  padding: 16px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--panel-border);
}
.preview-video,
.preview-empty {
  width: 100%;
  min-height: 320px;
  margin-top: 16px;
  border-radius: var(--radius-sm);
}
.preview-video {
  display: block;
  background: #0b0d1a;
}
.preview-empty {
  display: grid;
  place-items: center;
  background: rgba(11, 13, 26, 0.82);
  color: var(--text-faint);
}
.preview-notes {
  display: grid;
  gap: 14px;
}
.preview-notes article,
.info-banner {
  padding: 16px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--panel-border);
}
.preview-notes span {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--text-faint);
}
.render-progress {
  margin-top: 16px;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
}
.param-summary {
  display: grid;
  gap: 8px;
  margin: 0;
}
.param-summary div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.param-summary dt,
.param-summary dd,
.info-banner p {
  margin: 0;
}
.empty-note,
.empty-inline {
  padding: 32px 0;
  text-align: center;
  color: var(--text-faint);
}
.tag.success {
  background: rgba(92, 214, 169, 0.1);
  color: var(--success);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
}

@media (max-width: 1100px) {
  .generation-layout,
  .generation-main {
    grid-template-columns: 1fr;
  }
}
</style>
