<!-- frontend/src/components/character/CharacterAssetsPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import PromptProfileCard from "@/components/common/PromptProfileCard.vue";
import StyleReferenceCard from "@/components/common/StyleReferenceCard.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import CharacterEditorModal from "./CharacterEditorModal.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { confirm as uiConfirm } from "@/composables/useConfirm";
import { ApiError, messageFor } from "@/utils/error";
import {
  getCharacterAssetLibraryAction,
  getCharacterAssetLibraryBadge
} from "@/utils/characterAssetLibrary";
import type { CharacterAsset } from "@/types";
import type { CharacterUpdate, JobState } from "@/types/api";

const store = useWorkbenchStore();
const {
  current,
  selectedCharacter,
  selectedCharacterId,
  activeCharacterPromptProfileJobId,
  activeCharacterStyleReferenceJobId,
  activeGenerateCharactersJobId,
  activeRegisterCharacterAssetJobId,
  activeRegisterCharacterAssetCharacterId,
  characterPromptProfileError,
  characterStyleReferenceError,
  generateCharactersError,
  registerCharacterAssetError
} = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const editorOpen = ref(false);
const rollbackOpen = ref(false);
const busy = ref(false);
const starting = ref(false);

const characterPromptProfile = computed(
  () => current.value?.characterPromptProfile ?? { draft: null, applied: null, status: "empty" as const }
);
const characterStyleReference = computed(() => ({
  imageUrl: current.value?.characterStyleReference?.imageUrl ?? null,
  prompt: current.value?.characterStyleReference?.prompt ?? null,
  status: current.value?.characterStyleReference?.status ?? ("empty" as const),
  error: characterStyleReferenceError.value ?? current.value?.characterStyleReference?.error ?? null
}));

function warnCharacterStageGate(message: string) {
  toast.warning(message, {
    action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
  });
}

const { job: promptProfileJob } = useJobPolling(activeCharacterPromptProfileJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markPromptProfileJobSucceeded("character");
      toast.success("角色统一视觉设定已生成");
    } catch (e) {
      store.markPromptProfileJobFailed("character", (e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "生成失败");
    store.markPromptProfileJobFailed("character", msg);
    toast.error(msg);
  }
});

const promptProfileJobLabel = computed(() => {
  const j = promptProfileJob.value;
  if (!j) return "正在生成角色统一视觉设定…";
  return j.total && j.total > 0
    ? `正在生成角色统一视觉设定… ${j.done}/${j.total}`
    : `正在生成角色统一视觉设定… ${j.progress}%`;
});

useJobPolling(activeCharacterStyleReferenceJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markStyleReferenceJobSucceeded("character");
      toast.success("统一角色形象参考图已生成");
    } catch (e) {
      store.markStyleReferenceJobFailed("character", (e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "生成失败");
    store.markStyleReferenceJobFailed("character", msg);
    toast.error(msg);
  }
});

// ---- 生成主 job 轮询(空态入口) ----
const { job: generateJob } = useJobPolling(activeGenerateCharactersJobId, {
  onProgress: () => void 0,
  onSuccess: async (job) => {
    const nextJobId = job.result?.next_job_id;
    if (job.kind === "extract_characters" && nextJobId) {
      store.attachGenerateCharactersJob(nextJobId);
      return;
    }
    try {
      await store.reload();
      store.markGenerateCharactersSucceeded();
      toast.success("角色已生成");
    } catch (e) {
      store.markGenerateCharactersFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const prefix = j?.kind === "extract_characters" ? "角色提取失败" : "角色出图失败";
    const detail =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "生成失败");
    const msg = `${prefix}: ${detail}`;
    store.markGenerateCharactersFailed(msg);
    toast.error(msg);
  }
});

const generateProgressLabel = computed(() => {
  const j = generateJob.value;
  if (!j) return "正在排队…";
  if (j.kind === "extract_characters") return "正在提取角色…";
  if (j.total && j.total > 0) return `正在生成角色… ${j.done}/${j.total}`;
  return `正在生成角色… ${j.progress}%`;
});

// ---- 入人像库异步 job 轮询 ----
const { job: registerAssetJob } = useJobPolling(activeRegisterCharacterAssetJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    try {
      await store.reload();
      store.markRegisterCharacterAssetSucceeded();
      toast.success("角色已入人像库");
    } catch (e) {
      store.markRegisterCharacterAssetFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "入库失败");
    store.markRegisterCharacterAssetFailed(msg);
    toast.error(msg);
  }
});

const registerAssetProgressLabel = computed(() => {
  const j = registerAssetJob.value;
  if (!j) return "正在排队…";
  const stepMap: Record<number, string> = {
    0: "创建资产组",
    1: "创建资产",
    2: "等待 Active",
    3: "完成"
  };
  return `正在入人像库… ${stepMap[j.done] ?? `${j.done}/3`}`;
});

// ---- 单项 regen 轮询(按当前选中项精确找回) ----
const activeCharacterRegenJobId = computed(() => {
  if (!selectedCharacterId.value) return null;
  return store.regenJobIdFor("character", selectedCharacterId.value);
});
const regenProgressByJobId = ref<Record<string, number>>({});

useJobPolling(activeCharacterRegenJobId, {
  onProgress: (job: JobState) => {
    regenProgressByJobId.value[job.id] = job.progress;
  },
  onSuccess: async () => {
    if (selectedCharacterId.value) {
      store.markRegenByKeySucceeded(`character:${selectedCharacterId.value}`);
    }
    await store.reload();
    toast.success("角色参考图已重生成");
  },
  onError: (j, err) => {
    if (selectedCharacterId.value) {
      store.markRegenByKeyFailed(`character:${selectedCharacterId.value}`);
    }
    const msg =
      j?.error_msg ??
      (err instanceof ApiError ? messageFor(err.code, err.message) : "重生成失败");
    toast.error(msg);
  }
});

// ---- 触发动作 ----
async function handleGenerate() {
  if (!flags.value.canGenerateCharacters) {
    warnCharacterStageGate("当前阶段不允许生成角色");
    return;
  }
  starting.value = true;
  try {
    await store.generateCharacters({});
  } catch (e) {
    const msg = e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败";
    store.markGenerateCharactersFailed(msg);
    toast.error(msg);
  } finally {
    starting.value = false;
  }
}

async function handleGeneratePromptProfile() {
  if (!flags.value.canEditCharacters) {
    warnCharacterStageGate("当前阶段不允许修改角色统一视觉设定");
    return;
  }
  try {
    await store.generatePromptProfile("character");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  }
}

async function handleGenerateStyleReference() {
  if (!flags.value.canEditCharacters) {
    warnCharacterStageGate("当前阶段不能生成角色风格母版");
    return;
  }
  try {
    await store.generateStyleReference("character");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  }
}

async function handleSavePromptProfile(prompt: string) {
  if (!flags.value.canEditCharacters) {
    warnCharacterStageGate("当前阶段不允许修改角色统一视觉设定");
    return;
  }
  try {
    await store.savePromptProfileDraft("character", prompt);
    toast.success("角色统一视觉设定草稿已保存");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "保存失败");
  }
}

async function handleClearPromptProfile() {
  if (!flags.value.canEditCharacters) {
    warnCharacterStageGate("当前阶段不允许修改角色统一视觉设定");
    return;
  }
  try {
    await store.clearPromptProfileDraft("character");
    toast.success("角色统一视觉设定草稿已清空");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "清空失败");
  }
}

async function handleRestorePromptProfile() {
  if (!flags.value.canEditCharacters) {
    warnCharacterStageGate("当前阶段不允许修改角色统一视觉设定");
    return;
  }
  try {
    await store.restoreAppliedPromptProfileDraft("character");
    toast.success("已恢复到已应用版本");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "恢复失败");
  }
}

async function handleConfirmPromptProfile() {
  if (!flags.value.canEditCharacters) {
    warnCharacterStageGate("当前阶段不允许确认角色统一视觉设定");
    return;
  }
  try {
    await store.confirmPromptProfileAndGenerate("character");
    toast.info("已按统一视觉设定提交角色生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  }
}

async function handleSkipPromptProfile() {
  if (!flags.value.canGenerateCharacters) {
    warnCharacterStageGate("当前阶段不允许生成角色");
    return;
  }
  try {
    await store.skipPromptProfileAndGenerate("character");
    toast.info("已跳过统一视觉设定，直接生成角色");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  }
}

function openEdit() {
  if (!flags.value.canEditCharacters) {
    toast.warning("当前阶段不允许编辑角色,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  editorOpen.value = true;
}

async function handleEditSubmit(payload: CharacterUpdate) {
  if (!selectedCharacter.value) return;
  busy.value = true;
  try {
    await store.patchCharacter(selectedCharacter.value.id, payload);
    toast.success("角色已保存");
    editorOpen.value = false;
  } catch (e) {
    if (e instanceof ApiError && e.code === 40301) {
      toast.warning("当前阶段不允许编辑角色,如需修改请回退阶段", {
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
  if (!selectedCharacter.value) return;
  if (!flags.value.canEditCharacters) {
    toast.warning("当前阶段不允许编辑角色,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  busy.value = true;
  try {
    await store.regenerateCharacter(selectedCharacter.value.id);
    toast.info("已触发重生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败");
  } finally {
    busy.value = false;
  }
}

async function handleRegisterAsset() {
  if (!selectedCharacter.value) return;
  if (!flags.value.canRegisterCharacterAsset) {
    toast.warning("当前阶段不允许执行入人像库", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return;
  }
  const ok = await uiConfirm({
    title: "入人像库",
    body: "将当前角色参考图异步注册到人像库，约 10-120 秒。入库不会锁定角色，也不会推进项目阶段。",
    confirmText: "确认入库",
    danger: false
  });
  if (!ok) return;
  busy.value = true;
  try {
    await store.registerCharacterAsset(selectedCharacter.value.id);
    toast.info("已提交入人像库任务");
  } catch (e) {
    if (e instanceof ApiError && e.code === 42201) {
      toast.error(messageFor(42201, e.message));
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("入库失败");
    }
  } finally {
    busy.value = false;
  }
}

async function handleConfirmStage() {
  if (!flags.value.canConfirmCharacters) {
    toast.warning("当前阶段不允许进入场景设定");
    return;
  }
  busy.value = true;
  try {
    await store.confirmCharactersStage();
    toast.success("已进入场景设定");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "确认失败");
  } finally {
    busy.value = false;
  }
}

// ---- UI helpers ----
function badgeFor(c: CharacterAsset): string | null {
  return getCharacterAssetLibraryBadge(c);
}

const selectedCharacterAssetAction = computed(() =>
  selectedCharacter.value
    ? getCharacterAssetLibraryAction(selectedCharacter.value)
    : { label: "入人像库", disabled: false }
);

const canStartGenerate = computed(
  () =>
    flags.value.canGenerateCharacters &&
    (current.value?.characters.length ?? 0) === 0 &&
    !activeGenerateCharactersJobId.value
);

const selectedRegenJobId = computed(() =>
  selectedCharacter.value
    ? store.regenJobIdFor("character", selectedCharacter.value.id)
    : null
);
const selectedHasRegenJob = computed(() => !!selectedRegenJobId.value);
const selectedRegenProgress = computed(() =>
  selectedRegenJobId.value ? regenProgressByJobId.value[selectedRegenJobId.value] ?? 0 : 0
);
const selectedFullBodyImageUrl = computed(
  () => selectedCharacter.value?.full_body_image_url ?? selectedCharacter.value?.reference_image_url ?? null
);
</script>

<template>
  <PanelSection v-if="current" kicker="03" title="角色设定">
    <template #actions>
      <button
        class="primary-btn"
        type="button"
        :disabled="busy || !flags.canConfirmCharacters"
        @click="handleConfirmStage"
      >
        确认进入场景设定
      </button>
    </template>

    <div class="profile-reference-layout">
      <PromptProfileCard
        title="角色统一视觉设定"
        description="先锁定项目级角色画风、脸型气质、服装材质和镜头语言，再生成角色参考图会更稳定。"
        :profile="characterPromptProfile"
        :editable="flags.canEditCharacters"
        :generating="!!activeCharacterPromptProfileJobId"
        :generate-job-label="promptProfileJobLabel"
        :generate-error="characterPromptProfileError"
        :submitting="starting || busy || !!activeGenerateCharactersJobId"
        @generate="handleGeneratePromptProfile"
        @save="handleSavePromptProfile"
        @clear="handleClearPromptProfile"
        @restore="handleRestorePromptProfile"
        @confirm="handleConfirmPromptProfile"
        @skip="handleSkipPromptProfile"
      />
      <StyleReferenceCard
        kind="character"
        :state="characterStyleReference"
        :disabled="!flags.canEditCharacters"
        :running="!!activeCharacterStyleReferenceJobId"
        @generate="handleGenerateStyleReference"
      />
    </div>

    <!-- 生成主 job 进度 -->
    <div v-if="activeGenerateCharactersJobId" class="gen-banner running">
      <div class="gen-head">
        <strong>{{ generateProgressLabel }}</strong>
      </div>
      <ProgressBar :value="generateJob?.progress ?? 0" />
    </div>

    <div v-else-if="activeRegisterCharacterAssetJobId" class="gen-banner running">
      <div class="gen-head">
        <strong>{{ registerAssetProgressLabel }}</strong>
      </div>
      <ProgressBar :value="registerAssetJob ? Math.round((registerAssetJob.done / 3) * 100) : 0" />
      <p class="hint">正在调用人像库, 约 10-120 秒。可继续浏览, 完成后会自动刷新。</p>
    </div>

    <!-- 生成失败 banner -->
    <div v-else-if="generateCharactersError" class="gen-banner error">
      <div class="gen-head">
        <strong>角色生成失败</strong>
        <button class="ghost-btn small" @click="handleGenerate">重试</button>
      </div>
      <p>{{ generateCharactersError }}</p>
    </div>

    <div v-else-if="registerCharacterAssetError" class="gen-banner error">
      <div class="gen-head">
        <strong>入人像库失败</strong>
        <button class="ghost-btn small" @click="handleRegisterAsset">重试</button>
      </div>
      <p>{{ registerCharacterAssetError }}</p>
    </div>

    <!-- 空态大按钮 -->
    <div v-else-if="canStartGenerate" class="empty-cta">
      <p>尚未生成角色 · 基于已确认分镜抽取项目中的角色并生成参考图</p>
      <button class="primary-btn large" :disabled="starting" @click="handleGenerate">
        {{ starting ? "启动中..." : "生成角色资产" }}
      </button>
    </div>
    <div v-else-if="!current.characters.length" class="empty-note">
      尚未生成角色 · 分镜生成并确认后可触发 AI 抽取
    </div>

    <!-- 列表 + 详情 -->
    <div v-if="current.characters.length" class="asset-browser">
      <div class="asset-list-panel">
        <div class="list-head">
          <strong>所有角色</strong>
          <span>{{ current.characters.length }} 个资产</span>
        </div>
        <div class="asset-list">
          <button
            v-for="character in current.characters"
            :key="character.id"
            class="asset-list-item"
            :class="{ active: selectedCharacterId === character.id }"
            type="button"
            @click="store.selectCharacter(character.id)"
          >
            <div class="list-item-head">
              <strong>{{ character.name }}</strong>
              <span v-if="badgeFor(character)" class="badge">{{ badgeFor(character) }}</span>
            </div>
            <small>{{ character.summary ?? "" }}</small>
          </button>
        </div>
      </div>

      <div v-if="selectedCharacter" class="asset-detail-panel">
        <div class="subpage-head">
          <div>
            <p class="panel-kicker">角色详情</p>
            <h3>{{ selectedCharacter.name }}</h3>
          </div>
          <span class="tag accent">{{ selectedCharacter.role }}</span>
        </div>

        <div class="asset-layout">
          <div class="character-image-pair">
            <figure class="asset-image-card">
              <img
                v-if="selectedFullBodyImageUrl"
                :src="selectedFullBodyImageUrl"
                alt="全身参考图"
                loading="lazy"
              />
              <div v-else class="asset-image-card__empty">等待生成全身图</div>
              <figcaption>全身参考图</figcaption>
            </figure>
            <figure class="asset-image-card">
              <img
                v-if="selectedCharacter.headshot_image_url"
                :src="selectedCharacter.headshot_image_url"
                alt="头像参考图"
                loading="lazy"
              />
              <div v-else class="asset-image-card__empty">等待生成头像图</div>
              <figcaption>头像参考图</figcaption>
            </figure>
          </div>

          <div class="asset-info">
            <article class="asset-copy">
              <label>角色描述</label>
              <p>{{ selectedCharacter.description || "(尚无描述)" }}</p>
            </article>

            <article class="asset-meta">
              <span>视频形象参考</span>
              <ul v-if="selectedCharacter.meta.length">
                <li v-for="meta in selectedCharacter.meta" :key="meta">{{ meta }}</li>
              </ul>
              <p v-else class="faint">暂无 meta</p>
            </article>

            <div class="asset-actions">
              <button
                class="ghost-btn"
                :disabled="busy || !flags.canEditCharacters"
                :title="flags.canEditCharacters ? '编辑描述' : '当前阶段不允许编辑角色,请回退阶段'"
                @click="openEdit"
              >
                编辑描述
              </button>
              <button
                class="ghost-btn"
                :disabled="busy || selectedHasRegenJob || !flags.canEditCharacters"
                :title="flags.canEditCharacters ? '重新生成参考图' : '当前阶段不允许编辑角色,请回退阶段'"
                @click="handleRegen"
              >
                {{ selectedHasRegenJob ? `重生成中…(${selectedRegenProgress}%)` : "重新生成参考图" }}
              </button>
              <button
                class="primary-btn"
                :disabled="
                  busy ||
                  !flags.canRegisterCharacterAsset ||
                  !!activeRegisterCharacterAssetJobId ||
                  selectedCharacterAssetAction.disabled
                "
                :title="flags.canRegisterCharacterAsset ? '入人像库' : '当前阶段不允许执行入人像库,请回退阶段'"
                @click="handleRegisterAsset"
              >
                {{
                  activeRegisterCharacterAssetCharacterId === selectedCharacter.id
                    ? "入库中..."
                    : selectedCharacterAssetAction.label
                }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <CharacterEditorModal
      :open="editorOpen"
      :character="selectedCharacter"
      :busy="busy"
      @close="editorOpen = false"
      @submit="handleEditSubmit"
    />

    <StageRollbackModal :open="rollbackOpen" @close="rollbackOpen = false" />
  </PanelSection>
</template>

<style scoped>
.gen-banner {
  margin-bottom: 16px;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--panel-border);
  background: rgba(255,255,255,0.03);
}
.gen-banner.error { border-color: var(--danger); }
.gen-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.empty-cta { text-align: center; padding: 32px 0 16px; }
.empty-cta p { color: var(--text-faint); margin-bottom: 16px; }
.list-item-head { display: flex; justify-content: space-between; align-items: center; }
.badge {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: var(--accent-dim); color: var(--accent);
}
.ref-image {
  position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
}
.asset-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.faint { color: var(--text-faint); font-size: 12px; }
.profile-reference-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.8fr);
  gap: 18px;
  align-items: start;
  margin-bottom: 18px;
}

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
.asset-layout { display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 24px; }
.character-image-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.asset-image-card {
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
  background: #0b0d1a;
}
.asset-image-card img {
  display: block;
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
}
.asset-image-card__empty {
  display: grid;
  aspect-ratio: 3 / 4;
  place-items: center;
  color: var(--text-faint);
  font-size: 13px;
}
.asset-image-card figcaption {
  padding: 9px 10px;
  color: var(--text-muted);
  font-size: 12px;
  background: rgba(255, 255, 255, 0.04);
}
.reference-stage { position: relative; min-height: 280px; border-radius: var(--radius-md); background: #0b0d1a; border: 1px solid var(--panel-border); overflow: hidden; }
.reference-badge { position: absolute; top: 12px; left: 12px; padding: 4px 8px; background: rgba(0,0,0,0.5); color: #fff; font-size: 10px; border-radius: 4px; z-index: 1; }
.silhouette { position: absolute; bottom: 0; left: 50%; transform: translateX(-50%); width: 120px; height: 200px; background: linear-gradient(180deg, #333, #111); border-radius: 60px 60px 0 0; }
.asset-info { display: flex; flex-direction: column; gap: 20px; }
.asset-copy label { display: block; font-size: 12px; color: var(--accent); margin-bottom: 8px; }
.asset-copy p { margin: 0; font-size: 14px; color: var(--text-muted); line-height: 1.6; }
.asset-meta span { display: block; font-size: 12px; color: var(--text-faint); margin-bottom: 10px; }
.asset-meta ul { margin: 0; padding-left: 18px; font-size: 13px; color: var(--text-muted); line-height: 1.6; }
.tag.accent { background: var(--accent-dim); color: var(--accent); padding: 4px 10px; border-radius: 999px; font-size: 12px; }
.empty-note { padding: 40px 0; text-align: center; color: var(--text-faint); font-size: 14px; }

@media (max-width: 1100px) {
  .profile-reference-layout,
  .asset-browser,
  .asset-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .character-image-pair {
    grid-template-columns: 1fr;
  }
}
</style>
