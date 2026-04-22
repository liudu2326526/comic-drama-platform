<!-- frontend/src/components/setup/ProjectSetupPanel.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import ProgressBar from "@/components/common/ProgressBar.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useJobPolling } from "@/composables/useJobPolling";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";

const store = useWorkbenchStore();
const { current, activeParseJobId, parseError } = storeToRefs(store);
const toast = useToast();

const startingParse = ref(false);

const canStartParse = computed(
  () =>
    current.value?.stage_raw === "draft" &&
    current.value.storyboards.length === 0 &&
    !activeParseJobId.value
);

// activeParseJobId 已是 storeToRefs 返回的 Ref<string | null>,直接传给 useJobPolling
const { job } = useJobPolling(activeParseJobId, {
  onProgress: () => {
    // 进度推进,UI 自动响应 job.value
  },
  onSuccess: async () => {
    try {
      await store.reload();
      store.markParseSucceeded();
      toast.success("分镜已生成");
    } catch (e) {
      store.markParseFailed((e as Error).message);
    }
  },
  onError: (j, err) => {
    const msg =
      j?.error_msg ?? (err instanceof ApiError ? messageFor(err.code, err.message) : "解析失败");
    store.markParseFailed(msg);
    toast.error(msg);
  }
});

async function triggerParse() {
  if (!current.value || startingParse.value) return;
  startingParse.value = true;
  try {
    await store.startParse(current.value.id);
  } catch (e) {
    const msg = e instanceof ApiError ? messageFor(e.code, e.message) : "触发失败";
    store.markParseFailed(msg);
    toast.error(msg);
  } finally {
    startingParse.value = false;
  }
}

const progressLabel = computed(() => {
  const j = job.value;
  if (!j) return "正在排队…";
  if (j.total && j.total > 0) return `正在解析小说… ${j.done}/${j.total}`;
  return `正在解析小说… ${j.progress}%`;
});
</script>

<template>
  <PanelSection v-if="current" kicker="新建项目" :title="current.name">
    <template #actions>
      <span v-if="current.genre" class="tag warm">{{ current.genre }}</span>
      <span v-if="current.ratio" class="tag">{{ current.ratio }}</span>
      <span v-if="current.suggestedShots" class="tag">{{ current.suggestedShots }}</span>
    </template>

    <!-- 解析进行中 -->
    <div v-if="activeParseJobId" class="parse-banner running">
      <div class="parse-banner-head">
        <strong>{{ progressLabel }}</strong>
        <span v-if="job?.kind">job: {{ job.kind }}</span>
      </div>
      <ProgressBar :value="job?.progress ?? 0" />
    </div>

    <!-- 解析失败 -->
    <div v-else-if="parseError" class="parse-banner error">
      <div class="parse-banner-head">
        <strong>分镜解析失败</strong>
        <button class="ghost-btn small" @click="triggerParse">重试</button>
      </div>
      <p>{{ parseError }}</p>
    </div>

    <!-- 空态大按钮 -->
    <div v-else-if="canStartParse" class="empty-cta">
      <p>尚未生成分镜 · 点击下方按钮触发 AI 解析</p>
      <button class="primary-btn large" :disabled="startingParse" @click="triggerParse">
        {{ startingParse ? "启动中..." : "开始拆分分镜" }}
      </button>
    </div>

    <div class="project-setup">
      <div class="story-input-card">
        <label>小说内容输入</label>
        <textarea :value="current.story" readonly />
        <div v-if="current.parsedStats?.length" class="input-footer">
          <span v-for="stat in current.parsedStats" :key="stat">{{ stat }}</span>
        </div>
      </div>

      <div class="setup-side">
        <article v-if="current.setupParams?.length" class="mini-card">
          <span>项目参数</span>
          <ul>
            <li v-for="item in current.setupParams" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article v-if="current.summary" class="mini-card gradient-card">
          <span>AI 解析摘要</span>
          <p>{{ current.summary }}</p>
        </article>
      </div>
    </div>
  </PanelSection>
</template>

<style scoped>
.project-setup {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.95fr);
  gap: 18px;
}
.story-input-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.story-input-card textarea {
  min-height: 240px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  color: var(--text-muted);
  padding: 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.6;
}
.input-footer {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-faint);
}
.setup-side {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.mini-card {
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.mini-card span {
  display: block;
  font-size: 12px;
  color: var(--text-faint);
  text-transform: uppercase;
  margin-bottom: 12px;
}
.mini-card ul {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  color: var(--text-muted);
}
.gradient-card {
  background: linear-gradient(135deg, rgba(138, 140, 255, 0.05), rgba(255, 255, 255, 0.02));
}
.tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}
.tag.warm {
  color: var(--warning);
  background: rgba(241, 163, 75, 0.1);
}
.parse-banner {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--panel-border);
  margin-bottom: 18px;
  background: rgba(255, 255, 255, 0.03);
}
.parse-banner.running {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.parse-banner.error {
  background: rgba(240, 89, 89, 0.08);
  border-color: var(--danger);
}
.parse-banner-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  color: var(--text-primary);
  font-size: 13px;
}
.parse-banner p {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}
.empty-cta {
  padding: 32px;
  text-align: center;
  background: var(--accent-dim);
  border: 1px dashed var(--accent);
  border-radius: var(--radius-md);
  margin-bottom: 18px;
}
.empty-cta p {
  margin: 0 0 16px 0;
  color: var(--text-muted);
  font-size: 14px;
}
.primary-btn.large {
  font-size: 15px;
  padding: 12px 32px;
  border-radius: var(--radius-sm);
  border: none;
  background: var(--accent);
  color: #0b0d1a;
  font-weight: 600;
  cursor: pointer;
}
.primary-btn.large:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ghost-btn.small {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  cursor: pointer;
}
</style>
