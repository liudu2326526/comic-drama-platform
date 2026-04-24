<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import ReferenceMentionMenu from "@/components/generation/ReferenceMentionMenu.vue";
import ReferencePickerModal from "@/components/generation/ReferencePickerModal.vue";
import RenderVersionHistory from "@/components/generation/RenderVersionHistory.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";
import type {
  RenderSubmitReference,
  ReferenceAssetCreate,
  ReferenceCandidate,
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
const pickerOpen = ref(false);
const mentionOpen = ref(false);
const submitting = ref(false);
const loadingDraft = ref(false);
const draftPrompt = ref("");
const draftReferences = ref<RenderSubmitReference[]>([]);
const protectedMentionBase = ref("");
const lastStablePrompt = ref("");
const promptEl = ref<HTMLTextAreaElement | null>(null);
const MAX_REFERENCES = 6;
const MENTION_TRIGGER_RE = /@[^@\s，。！？、；：,.!?;:（）()【】《》“”"']{0,30}$/;

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
const renderProgressLabel = computed(() => {
  if (!selectedRenderShot.value) return "";
  const remain = selectedRenderShot.value.estimatedRemainingSeconds;
  const source = selectedRenderShot.value.estimatedSource;
  const base = remain === null || remain === undefined ? "" : `预计剩余约 ${remain} 秒`;
  if (!source?.startsWith("recent_")) return base;
  const count = source.replace("recent_", "");
  return `${base} · 基于最近 ${count} 条同类任务`;
});
const selectedCandidates = computed(() =>
  selectedRenderShot.value ? store.referenceCandidatesFor(selectedRenderShot.value.shotId) : []
);
const generateVideoDisabled = computed(() => {
  if (!selectedRenderShot.value || !flags.value.canRender) return true;
  const isActiveShot = !!activeRenderJobId.value && activeRenderShotId.value === selectedRenderShot.value.shotId;
  return isActiveShot || !draftPrompt.value.trim() || draftReferences.value.length === 0;
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
    duration: snapshot.duration === null || snapshot.duration === undefined ? null : Number(snapshot.duration),
    resolution: String(snapshot.resolution ?? "480p") as ShotVideoResolution,
    modelType: String(snapshot.model_type ?? "fast") as ShotVideoModelType,
  };
}

function syncDraftFromStore() {
  const shotId = selectedRenderShot.value?.shotId;
  if (!shotId) {
    draftPrompt.value = "";
    lastStablePrompt.value = "";
    draftReferences.value = [];
    return;
  }
  const draft = store.renderDraftFor(shotId);
  draftPrompt.value = draft?.prompt ?? "";
  lastStablePrompt.value = draftPrompt.value;
  draftReferences.value = (draft?.references ?? []).map((item) => ({
    id: item.id,
    kind: item.kind,
    source_id: item.source_id,
    name: item.name,
    image_url: item.image_url,
    alias: item.alias ?? item.name,
    mention_key: item.mention_key ?? item.id,
    origin: item.origin ?? item.kind,
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
        lastStablePrompt.value = draft.prompt;
        draftReferences.value = draft.references.map((item) => ({
          id: item.id,
          kind: item.kind,
          source_id: item.source_id,
          name: item.name,
          image_url: item.image_url,
          alias: item.alias ?? item.name,
          mention_key: item.mention_key ?? item.id,
          origin: item.origin ?? item.kind,
        }));
      } catch {
        // noop
      }
    }
    if (!store.referenceCandidatesFor(shotId).length) {
      try {
        await store.fetchReferenceCandidates(shotId);
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
  onProgress: (job) => store.applyRenderJobProgress(job),
  onSuccess: async () => {
    const shotId = activeDraftShotId.value;
    if (!shotId) {
      return;
    }
    try {
      const draft = await store.fetchRenderDraft(shotId);
      draftPrompt.value = draft.prompt;
      lastStablePrompt.value = draft.prompt;
      draftReferences.value = draft.references.map((item) => ({
        id: item.id,
        kind: item.kind,
        source_id: item.source_id,
        name: item.name,
        image_url: item.image_url,
        alias: item.alias ?? item.name,
        mention_key: item.mention_key ?? item.id,
        origin: item.origin ?? item.kind,
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

function onPromptInput(value: string, cursor = value.length) {
  if (!selectedRenderShot.value) return;
  const replacedByAt = value === "@" && draftPrompt.value.length > 1;
  if (replacedByAt) protectedMentionBase.value = draftPrompt.value;
  const next = replacedByAt ? `${draftPrompt.value}@` : value;
  const nextCursor = replacedByAt ? next.length : cursor;
  if (!isMentionTriggerActive(next, nextCursor)) protectedMentionBase.value = "";
  draftPrompt.value = next;
  if (next.length > 1) lastStablePrompt.value = isMentionTriggerActive(next, nextCursor) ? next.slice(0, nextCursor - 1) : next;
  mentionOpen.value = isMentionTriggerActive(next, nextCursor);
  store.updateRenderDraft(selectedRenderShot.value.shotId, { prompt: next });
}

function onPromptFocus(event: FocusEvent) {
  const textarea = event.target as HTMLTextAreaElement;
  mentionOpen.value = isMentionTriggerActive(draftPrompt.value, textarea.selectionStart ?? draftPrompt.value.length);
}

function onPromptKeydown(event: KeyboardEvent) {
  if (event.key !== "@" || !selectedRenderShot.value) return;
  const textarea = event.target as HTMLTextAreaElement;
  const start = textarea.selectionStart ?? 0;
  const end = textarea.selectionEnd ?? start;
  if (start !== 0 || end !== draftPrompt.value.length || draftPrompt.value.length === 0) return;

  event.preventDefault();
  protectedMentionBase.value = draftPrompt.value;
  const next = `${draftPrompt.value}@`;
  onPromptInput(next);
  mentionOpen.value = true;
  requestAnimationFrame(() => {
    textarea.focus();
    textarea.setSelectionRange(next.length, next.length);
  });
}

function removeReference(id: string) {
  if (!selectedRenderShot.value) return;
  const item = draftReferences.value.find((ref) => ref.id === id);
  const label = item?.alias ?? item?.name ?? "";
  if (label && draftPrompt.value.includes(`@${label}`) && !window.confirm("该参考图已在提示词中被 @ 引用，确认删除？")) {
    return;
  }
  draftReferences.value = draftReferences.value.filter((item) => item.id !== id);
  store.updateRenderDraft(selectedRenderShot.value.shotId, { references: draftReferences.value as never });
}

function addReference(item: ReferenceCandidate) {
  if (!selectedRenderShot.value || draftReferences.value.length >= MAX_REFERENCES) return;
  if (draftReferences.value.some((ref) => ref.id === item.id)) return;
  draftReferences.value = disambiguateAliases([...draftReferences.value, candidateToReference(item)]);
  store.updateRenderDraft(selectedRenderShot.value.shotId, { references: draftReferences.value as never });
  pickerOpen.value = false;
}

async function registerManualReference(payload: ReferenceAssetCreate) {
  if (!selectedRenderShot.value) return;
  try {
    const item = await store.registerManualReference(selectedRenderShot.value.shotId, payload);
    addReference(item);
    pickerOpen.value = false;
    toast.success("已加入参考图");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "加入参考图失败");
  }
}

function candidateToReference(item: ReferenceCandidate): RenderSubmitReference {
  return {
    id: item.id,
    kind: item.kind,
    source_id: item.source_id,
    name: item.name,
    image_url: item.image_url,
    alias: item.alias,
    mention_key: item.mention_key,
    origin: item.origin,
  };
}

function disambiguateAliases(items: RenderSubmitReference[]): RenderSubmitReference[] {
  const counts = new Map<string, number>();
  return items.map((item) => {
    const base = item.alias ?? item.name;
    const next = (counts.get(base) ?? 0) + 1;
    counts.set(base, next);
    return { ...item, alias: next === 1 ? base : `${base}-${item.kind}` };
  });
}

function insertMention(item: RenderSubmitReference) {
  const label = item.alias ?? item.name;
  const textarea = promptEl.value;
  const mention = `@${label} `;
  if (!textarea) {
    onPromptInput(`${draftPrompt.value}${mention}`);
    return;
  }
  const start = textarea.selectionStart ?? draftPrompt.value.length;
  const end = textarea.selectionEnd ?? start;
  const recoveredBase = protectedMentionBase.value || (draftPrompt.value === "@" ? lastStablePrompt.value : "");
  const hasRecoveredBase = recoveredBase && draftPrompt.value.endsWith("@");
  const value = hasRecoveredBase ? `${recoveredBase}@` : draftPrompt.value;
  const { next, position } = buildMentionInsertedPrompt(
    value,
    hasRecoveredBase ? value.length : start,
    hasRecoveredBase ? value.length : end,
    mention
  );
  onPromptInput(next, position);
  protectedMentionBase.value = "";
  mentionOpen.value = false;
  requestAnimationFrame(() => {
    textarea.focus();
    textarea.setSelectionRange(position, position);
  });
}

function buildMentionInsertedPrompt(value: string, selectionStart: number, selectionEnd: number, mention: string) {
  let start = selectionStart;
  let end = selectionEnd;
  if (
    start === 0 &&
    (
      end === value.length ||
      (value.endsWith("@") && (end === value.length - 1 || value.length > 1))
    ) &&
    value.length > 0
  ) {
    start = value.length;
    end = value.length;
  }
  const prefix = value.slice(0, start);
  const activeMention = prefix.match(MENTION_TRIGGER_RE)?.[0] ?? "";
  const insertStart = activeMention ? start - activeMention.length : start;
  const next = `${value.slice(0, insertStart)}${mention}${value.slice(end)}`;
  return { next, position: insertStart + mention.length };
}

function isMentionTriggerActive(value: string, cursor = value.length) {
  return MENTION_TRIGGER_RE.test(value.slice(0, cursor));
}

function moveReference(id: string, direction: -1 | 1) {
  if (!selectedRenderShot.value) return;
  const index = draftReferences.value.findIndex((item) => item.id === id);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= draftReferences.value.length) return;
  const next = [...draftReferences.value];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  draftReferences.value = next;
  store.updateRenderDraft(selectedRenderShot.value.shotId, { references: draftReferences.value as never });
}

function persistCurrentDraft() {
  if (!selectedRenderShot.value) return;
  store.updateRenderDraft(selectedRenderShot.value.shotId, {
    prompt: draftPrompt.value,
    references: draftReferences.value as never,
  });
}

async function generateDraft() {
  if (!selectedRenderShot.value || !flags.value.canRender) return;
  persistCurrentDraft();
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
    persistCurrentDraft();
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
            <small v-if="renderProgressLabel">{{ renderProgressLabel }}</small>
          </div>

          <div class="reference-head">
            <strong>参考图</strong>
            <span>{{ draftReferences.length }}/{{ MAX_REFERENCES }} 张</span>
          </div>
          <div v-if="draftReferences.length" class="reference-rail">
            <article v-for="item in draftReferences" :key="item.id" class="reference-chip">
              <button class="thumb-btn" type="button" @click="insertMention(item)">
                <img :src="item.image_url" :alt="item.alias ?? item.name" />
              </button>
              <strong>{{ item.alias ?? item.name }}</strong>
              <small>{{ item.kind }}</small>
              <div class="reference-tools">
                <button class="ghost-btn tiny" type="button" @click="moveReference(item.id, -1)">↑</button>
                <button class="ghost-btn tiny" type="button" @click="moveReference(item.id, 1)">↓</button>
                <button class="ghost-btn tiny" type="button" @click="removeReference(item.id)">删除</button>
              </div>
            </article>
            <button
              class="add-reference"
              type="button"
              :disabled="draftReferences.length >= MAX_REFERENCES"
              @click="pickerOpen = true"
            >
              添加
            </button>
          </div>
          <div v-else class="empty-inline">
            至少保留 1 张参考图后才能生成视频。
            <button class="ghost-btn small" type="button" @click="pickerOpen = true">添加参考图</button>
          </div>

          <label class="field-label" for="draft-prompt">镜头提示词</label>
          <textarea
            id="draft-prompt"
            ref="promptEl"
            data-testid="draft-prompt"
            :value="draftPrompt"
            class="prompt-input"
            rows="8"
            placeholder="先生成草稿，再按需要调整镜头提示词"
            @keydown="onPromptKeydown"
            @input="
              onPromptInput(
                ($event.target as HTMLTextAreaElement).value,
                ($event.target as HTMLTextAreaElement).selectionStart ?? undefined
              )
            "
            @focus="onPromptFocus"
            @blur="mentionOpen = false"
          />
          <ReferenceMentionMenu
            :open="mentionOpen"
            :items="draftReferences"
            @select="insertMention"
          />
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
    <ReferencePickerModal
      :open="pickerOpen"
      :candidates="selectedCandidates"
      :selected="draftReferences"
      :max-count="MAX_REFERENCES"
      @close="pickerOpen = false"
      @add="addReference"
      @register="registerManualReference"
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
}
.reference-rail {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.reference-chip {
  flex: 0 0 116px;
  min-width: 116px;
  padding: 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.02);
}
.thumb-btn {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
}
.reference-chip img {
  display: block;
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 6px;
}
.reference-chip strong,
.reference-chip small {
  display: block;
  overflow: hidden;
  margin-top: 6px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.reference-chip small {
  color: var(--text-faint);
}
.reference-tools {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}
.ghost-btn.tiny {
  padding: 4px 6px;
  font-size: 11px;
}
.add-reference {
  flex: 0 0 82px;
  min-height: 116px;
  border: 1px dashed var(--panel-border);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-muted);
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
.render-progress small {
  display: block;
  margin-top: 8px;
  color: var(--text-faint);
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
