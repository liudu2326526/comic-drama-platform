<!-- frontend/src/components/storyboard/StoryboardPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import StoryboardEditorModal from "./StoryboardEditorModal.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useToast } from "@/composables/useToast";
import { confirm as uiConfirm } from "@/composables/useConfirm";
import { ApiError, messageFor } from "@/utils/error";
import type { StoryboardShot } from "@/types";
import type { StoryboardCreateRequest, StoryboardUpdateRequest } from "@/types/api";

const store = useWorkbenchStore();
const { current, currentShot, selectedShotId } = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const editorOpen = ref(false);
const editorMode = ref<"create" | "edit">("create");
const editorInitial = ref<StoryboardShot | null>(null);
const rollbackOpen = ref(false);
const busy = ref(false);

const lockedTip = "当前阶段已锁定,如需修改请 回退阶段";
// 已确认后想改分镜需回退到 draft 或 storyboard_ready(回退 modal 内收敛目标)
const alreadyConfirmedTip = "已确认。如需修改分镜请 回退阶段";

const confirmLabel = computed(() => {
  const n = current.value?.storyboards.length ?? 0;
  return `确认 ${n} 个镜头`;
});

function guardEdit(): boolean {
  if (flags.value.canEditStoryboards) return true;
  toast.warning(lockedTip, {
    action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
  });
  return false;
}

function openCreate() {
  if (!guardEdit()) return;
  editorMode.value = "create";
  editorInitial.value = null;
  editorOpen.value = true;
}

function openEdit(shot: StoryboardShot) {
  if (!guardEdit()) return;
  editorMode.value = "edit";
  editorInitial.value = shot;
  editorOpen.value = true;
}

async function handleSubmit(
  payload: StoryboardCreateRequest | StoryboardUpdateRequest
) {
  busy.value = true;
  try {
    if (editorMode.value === "create") {
      await store.createShot(payload as StoryboardCreateRequest);
      toast.success("镜头已新增");
    } else if (editorInitial.value) {
      await store.updateShot(editorInitial.value.id, payload as StoryboardUpdateRequest);
      toast.success("镜头已保存");
    }
    editorOpen.value = false;
  } catch (e) {
    if (e instanceof ApiError && e.code === 40301) {
      toast.warning(lockedTip, {
        action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
      });
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("操作失败");
    }
  } finally {
    busy.value = false;
  }
}

async function removeShot(shot: StoryboardShot) {
  if (!guardEdit()) return;
  const ok = await uiConfirm({
    title: "删除镜头",
    body: `确定删除镜头 ${String(shot.idx).padStart(2, "0")} 「${shot.title}」?该操作不可撤销。`,
    confirmText: "删除",
    danger: true
  });
  if (!ok) return;
  busy.value = true;
  try {
    await store.deleteShot(shot.id);
    toast.success("镜头已删除");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "删除失败");
  } finally {
    busy.value = false;
  }
}

async function moveUp(shot: StoryboardShot) {
  if (!guardEdit()) return;
  busy.value = true;
  try {
    await store.moveShotUp(shot.id);
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "重排失败");
  } finally {
    busy.value = false;
  }
}
async function moveDown(shot: StoryboardShot) {
  if (!guardEdit()) return;
  busy.value = true;
  try {
    await store.moveShotDown(shot.id);
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "重排失败");
  } finally {
    busy.value = false;
  }
}

const shots = computed(() => current.value?.storyboards ?? []);
const isFirst = (shot: StoryboardShot) => shots.value[0]?.id === shot.id;
const isLast = (shot: StoryboardShot) => shots.value[shots.value.length - 1]?.id === shot.id;

// 空态文案按 stage 区分:draft 指向 setup panel 的大按钮;其他 stage 说明需回退或新增
const emptyHint = computed(() => {
  if (current.value?.stage_raw === "draft") {
    return "尚未生成分镜 · 请先在上方 Setup Panel 点 '开始拆分分镜'";
  }
  return "当前项目还没有镜头 · 点顶部 '+ 新增镜头' 开始手动编排,或回退到 draft 重新解析";
});

const confirming = ref(false);
const alreadyConfirmed = computed(() => current.value?.stage_raw !== "draft");
const canConfirm = computed(
  () =>
    current.value?.stage_raw === "draft" &&
    shots.value.length > 0 &&
    !confirming.value
);
const confirmTooltip = computed(() => {
  if (alreadyConfirmed.value) return alreadyConfirmedTip;
  if (shots.value.length === 0) return "请先新增镜头";
  return "";
});

async function onConfirm() {
  if (!canConfirm.value) return;
  const ok = await uiConfirm({
    title: "确认分镜",
    body: `将确认 ${shots.value.length} 个镜头并进入下一阶段。确认后若需修改需先回退到 draft。`,
    confirmText: "确认",
    danger: false
  });
  if (!ok) return;
  confirming.value = true;
  try {
    await store.confirmStoryboards();
    toast.success("分镜已确认,进入角色阶段");
  } catch (e) {
    if (e instanceof ApiError && e.code === 40901) {
      toast.warning(messageFor(e.code, e.message));
    } else if (e instanceof ApiError) {
      toast.error(messageFor(e.code, e.message));
    } else {
      toast.error("确认失败");
    }
  } finally {
    confirming.value = false;
  }
}
</script>

<template>
  <PanelSection v-if="current" kicker="02" title="分镜工作台">
    <template #actions>
      <button
        class="ghost-btn"
        type="button"
        :disabled="busy"
        :title="flags.canEditStoryboards ? '' : lockedTip"
        @click="openCreate"
      >
        + 新增镜头
      </button>
      <button
        class="primary-btn"
        type="button"
        :disabled="!canConfirm || alreadyConfirmed"
        :title="confirmTooltip"
        @click="onConfirm"
      >
        {{ alreadyConfirmed ? "已确认" : confirming ? "确认中..." : confirmLabel }}
      </button>
    </template>

    <div v-if="!shots.length" class="empty-note">
      {{ emptyHint }}
    </div>
    <div v-else class="storyboard-layout">
      <div class="storyboard-grid">
        <article
          v-for="shot in shots"
          :key="shot.id"
          class="story-card"
          :class="{ active: selectedShotId === shot.id }"
          @click="store.selectShot(shot.id)"
        >
          <div class="card-head">
            <span>{{ String(shot.idx).padStart(2, "0") }}</span>
            <div class="card-actions" @click.stop>
              <button
                class="icon-btn"
                :disabled="!flags.canEditStoryboards || busy || isFirst(shot)"
                :title="flags.canEditStoryboards ? '上移' : lockedTip"
                @click="moveUp(shot)"
              >↑</button>
              <button
                class="icon-btn"
                :disabled="!flags.canEditStoryboards || busy || isLast(shot)"
                :title="flags.canEditStoryboards ? '下移' : lockedTip"
                @click="moveDown(shot)"
              >↓</button>
              <button
                class="icon-btn"
                :disabled="busy"
                :title="flags.canEditStoryboards ? '编辑' : lockedTip"
                @click="openEdit(shot)"
              >✎</button>
              <button
                class="icon-btn danger"
                :disabled="busy"
                :title="flags.canEditStoryboards ? '删除' : lockedTip"
                @click="removeShot(shot)"
              >✕</button>
            </div>
          </div>
          <strong>{{ shot.title }}</strong>
          <p>{{ shot.description }}</p>
        </article>
      </div>

      <div v-if="currentShot" class="storyboard-detail">
        <div class="detail-title">
          <h3>
            当前镜头：{{ String(currentShot.idx).padStart(2, "0") }}
            {{ currentShot.title }}
          </h3>
          <span v-if="currentShot.duration_sec">时长建议 {{ currentShot.duration_sec }}s</span>
        </div>
        <p>{{ currentShot.detail }}</p>
        <div class="detail-tags">
          <span v-for="tag in currentShot.tags" :key="tag">{{ tag }}</span>
        </div>
      </div>
    </div>

    <StoryboardEditorModal
      :open="editorOpen"
      :mode="editorMode"
      :initial="editorInitial"
      @close="editorOpen = false"
      @submit="handleSubmit"
    />
    <StageRollbackModal :open="rollbackOpen" @close="rollbackOpen = false" />
  </PanelSection>
</template>

<style scoped>
.storyboard-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.9fr);
  gap: 18px;
}
.storyboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.story-card {
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 160ms;
}
.story-card.active {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.card-head span {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(138, 140, 255, 0.1);
  color: var(--accent);
  font-size: 12px;
}
.card-actions {
  display: flex;
  gap: 4px;
}
.icon-btn {
  width: 26px;
  height: 26px;
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
}
.icon-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.icon-btn.danger:hover:not(:disabled) {
  color: var(--danger);
  border-color: var(--danger);
}
.story-card strong {
  display: block;
  font-size: 15px;
  margin-bottom: 8px;
}
.story-card p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}
.storyboard-detail {
  padding: 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.detail-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.detail-title h3 {
  margin: 0;
  font-size: 18px;
}
.detail-title span {
  font-size: 12px;
  color: var(--text-faint);
}
.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.detail-tags span {
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-muted);
}
.empty-note {
  padding: 40px 0;
  text-align: center;
  color: var(--text-faint);
  font-size: 14px;
}
.primary-btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: none;
  background: var(--accent);
  color: #0b0d1a;
  font-weight: 600;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ghost-btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  cursor: pointer;
}
</style>
