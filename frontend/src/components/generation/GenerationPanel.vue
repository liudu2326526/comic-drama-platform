<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import RenderRetryBanner from "@/components/generation/RenderRetryBanner.vue";
import RenderVersionHistory from "@/components/generation/RenderVersionHistory.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";
import type { RenderSubmitReference } from "@/types/api";

const store = useWorkbenchStore();
const {
  current,
  selectedShotId,
  renderShots,
  activeRenderJobId,
  activeRenderShotId,
  renderHistoryLoadingShotId,
  renderError
} = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const draftPrompt = ref("");
const draftReferences = ref<RenderSubmitReference[]>([]);
const historyOpen = ref(false);
const submitting = ref(false);
const loadingDraft = ref(false);

const selectedRenderShot = computed(
  () =>
    renderShots.value.find((item) => item.shotId === selectedShotId.value) ??
    renderShots.value[0] ??
    null
);

const selectedVersions = computed(() =>
  selectedRenderShot.value ? store.renderVersionsFor(selectedRenderShot.value.shotId) : []
);

const currentVersion = computed(() =>
  selectedVersions.value.find((item) => item.is_current) ?? selectedVersions.value[0] ?? null
);

const previewImageUrl = computed(
  () => currentVersion.value?.image_url ?? selectedRenderShot.value?.imageUrl ?? null
);

const promptSnapshotText = computed(() =>
  currentVersion.value?.prompt_snapshot
    ? JSON.stringify(currentVersion.value.prompt_snapshot, null, 2)
    : current.value?.generationNotes?.input ?? ""
);

const versionErrorCode = computed(
  () => currentVersion.value?.error_code ?? selectedRenderShot.value?.errorCode ?? null
);
const versionErrorMsg = computed(
  () => currentVersion.value?.error_msg ?? selectedRenderShot.value?.errorMsg ?? renderError.value ?? null
);
const renderProgress = computed(() => {
  if (activeRenderShotId.value !== selectedRenderShot.value?.shotId) return 0;
  return selectedRenderShot.value?.progress ?? 0;
});
const isOtherShotRendering = computed(
  () => !!activeRenderJobId.value && activeRenderShotId.value !== selectedRenderShot.value?.shotId
);
const disableDraftActions = computed(
  () => !flags.value.canRender || !selectedRenderShot.value || isOtherShotRendering.value
);
const confirmDisabled = computed(
  () =>
    disableDraftActions.value ||
    loadingDraft.value ||
    submitting.value ||
    !draftPrompt.value.trim() ||
    draftReferences.value.length === 0
);

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
    image_url: item.image_url
  }));
}

watch(
  () => selectedRenderShot.value?.shotId,
  () => {
    syncDraftFromStore();
  },
  { immediate: true }
);

watch(
  () => selectedRenderShot.value?.shotId,
  async (shotId) => {
    if (!shotId) return;
    if (!store.renderVersionsFor(shotId).length) {
      try {
        await store.fetchRenderVersions(shotId);
      } catch {
        // 保持静默，避免切换镜头时连续弹错
      }
    }
  },
  { immediate: true }
);

useJobPolling(activeRenderJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      const shotId = activeRenderShotId.value;
      await store.reload();
      store.markRenderSucceeded();
      if (shotId) await store.fetchRenderVersions(shotId);
      toast.success("镜头生成完成");
    } catch (e) {
      store.markRenderFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "镜头生成失败");
    store.markRenderFailed(msg);
    toast.error(msg);
  }
});

function selectShot(shotId: string) {
  store.selectShot(shotId);
}

async function generateDraft() {
  if (!selectedRenderShot.value || disableDraftActions.value) return;
  loadingDraft.value = true;
  try {
    const draft = await store.fetchRenderDraft(selectedRenderShot.value.shotId);
    draftPrompt.value = draft.prompt;
    draftReferences.value = draft.references.map((item) => ({
      id: item.id,
      kind: item.kind,
      source_id: item.source_id,
      name: item.name,
      image_url: item.image_url
    }));
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "生成草稿失败");
  } finally {
    loadingDraft.value = false;
  }
}

function removeReference(id: string) {
  draftReferences.value = draftReferences.value.filter((item) => item.id !== id);
}

async function confirmRender() {
  if (!selectedRenderShot.value || confirmDisabled.value) return;
  if (!draftPrompt.value.trim()) {
    toast.warning("请先补充镜头提示词");
    return;
  }
  if (!draftReferences.value.length) {
    toast.warning("至少保留 1 张参考图后才能确认生成");
    return;
  }
  submitting.value = true;
  try {
    await store.confirmRenderShot(selectedRenderShot.value.shotId, {
      prompt: draftPrompt.value,
      references: draftReferences.value
    });
    toast.info("已提交镜头生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "提交生成失败");
  } finally {
    submitting.value = false;
  }
}

async function handleSelectVersion(renderId: string) {
  if (!selectedRenderShot.value) return;
  try {
    await store.selectRenderVersion(selectedRenderShot.value.shotId, renderId);
    historyOpen.value = false;
    toast.success("已切换当前版本");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "切换版本失败");
  }
}

async function handleLockShot() {
  if (!selectedRenderShot.value || !flags.value.canLockShot) return;
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

    <div v-if="!flags.canRender && !renderShots.length" class="empty-note">
      资产锁定后可开始镜头渲染
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
                      ? "生成中"
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
                :disabled="disableDraftActions || loadingDraft"
                @click="generateDraft"
              >
                {{ loadingDraft ? "草稿生成中..." : "生成草稿" }}
              </button>
              <button
                class="ghost-btn"
                type="button"
                :disabled="!selectedRenderShot || renderHistoryLoadingShotId === selectedRenderShot.shotId"
                @click="historyOpen = true"
              >
                查看历史版本
              </button>
              <button
                class="primary-btn"
                type="button"
                data-testid="confirm-render-btn"
                :disabled="confirmDisabled"
                @click="confirmRender"
              >
                {{ submitting ? "提交中..." : "确认生成" }}
              </button>
            </div>
          </div>

          <div v-if="activeRenderJobId && activeRenderShotId === selectedRenderShot.shotId" class="render-progress">
            <div class="progress-head">
              <strong>镜头生成中</strong>
              <span>{{ renderProgress }}%</span>
            </div>
            <ProgressBar :value="renderProgress" />
          </div>

          <RenderRetryBanner
            :error-code="versionErrorCode"
            :error-msg="versionErrorMsg"
            :shot-status="selectedRenderShot.shotStatus"
          />

          <label class="field-label" for="draft-prompt">镜头提示词</label>
          <textarea
            id="draft-prompt"
            data-testid="draft-prompt"
            v-model="draftPrompt"
            class="prompt-input"
            rows="8"
            placeholder="先生成草稿，再按需要调整镜头提示词"
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
          <div v-else class="empty-inline">至少保留 1 张参考图后才能确认生成。</div>
        </div>

        <div class="preview-panel">
          <div class="preview-frame">
            <div class="frame-caption">
              <span>Frame Preview</span>
              <strong>{{ selectedRenderShot.title }}</strong>
            </div>
            <img v-if="previewImageUrl" class="preview-image" :src="previewImageUrl" :alt="selectedRenderShot.title" />
            <div v-else class="preview-empty">当前还没有可预览的成功版本</div>
          </div>

          <div class="preview-notes">
            <article>
              <span>Prompt Snapshot</span>
              <pre>{{ promptSnapshotText || "(暂无快照)" }}</pre>
            </article>
            <article>
              <span>操作</span>
              <button
                class="primary-btn"
                type="button"
                :disabled="!flags.canLockShot || !selectedRenderShot.currentRenderId"
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
      :current-render-id="selectedRenderShot?.currentRenderId ?? null"
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
.preview-image,
.preview-empty {
  width: 100%;
  min-height: 320px;
  margin-top: 16px;
  border-radius: var(--radius-sm);
}
.preview-image {
  display: block;
  object-fit: cover;
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
.preview-notes article {
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
.preview-notes pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  color: var(--text-muted);
}
.render-progress {
  margin-top: 16px;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
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
