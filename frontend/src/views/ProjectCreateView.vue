<!-- frontend/src/views/ProjectCreateView.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import { useProjectsStore } from "@/store/projects";
import { useWorkbenchStore } from "@/store/workbench";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";

const form = ref({
  name: "",
  story: "",
  ratio: "9:16"
});
const savingDraft = ref(false);
const startingParse = ref(false);
const router = useRouter();
const toast = useToast();
const projects = useProjectsStore();
const workbench = useWorkbenchStore();

const storyLen = computed(() => form.value.story.trim().length);
const canSubmit = computed(() => form.value.name.trim().length > 0 && storyLen.value >= 200);
const isLongStory = computed(() => storyLen.value > 5000);

async function createOnly(): Promise<string | null> {
  const resp = await projects.createProject({
    name: form.value.name.trim(),
    story: form.value.story.trim(),
    ratio: form.value.ratio
  });
  return resp.id;
}

async function saveDraft() {
  if (!canSubmit.value || savingDraft.value) return;
  savingDraft.value = true;
  try {
    const id = await createOnly();
    if (!id) return;
    toast.success("项目草稿已保存");
    await router.push({ name: "workbench", params: { id } });
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "创建失败");
  } finally {
    savingDraft.value = false;
  }
}

async function startParse() {
  if (!canSubmit.value || startingParse.value) return;
  startingParse.value = true;
  let createdId: string | null = null;
  try {
    createdId = await createOnly();
    if (!createdId) return;
    await workbench.startParse(createdId);
    toast.success("已开始拆分分镜");
    await router.push({ name: "workbench", params: { id: createdId } });
  } catch (e) {
    // 如果项目已创建但 parse 失败,也跳到 workbench,让用户在 setup panel 重试
    if (createdId) {
      toast.warning(
        e instanceof ApiError ? messageFor(e.code, e.message) : "拆分未能启动,请在工作台重试"
      );
      await router.push({ name: "workbench", params: { id: createdId } });
    } else {
      toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "创建失败");
    }
  } finally {
    startingParse.value = false;
  }
}
</script>

<template>
  <div class="page-shell">
    <AppTopbar title="新建项目">
      <button class="ghost-btn" @click="$router.back()">返回</button>
    </AppTopbar>

    <form class="create-form" @submit.prevent>
      <label>
        <span>项目名</span>
        <input v-model="form.name" maxlength="128" placeholder="如:皇城夜雨" />
      </label>

      <div class="form-row">
        <label>
          <span>画幅比例</span>
          <select v-model="form.ratio">
            <option>9:16</option>
            <option>16:9</option>
            <option>1:1</option>
          </select>
        </label>
      </div>

      <label>
        <span>小说正文 ({{ storyLen }} 字, 需 ≥ 200 字)</span>
        <textarea v-model="form.story" rows="12" placeholder="粘贴完整小说正文..." />
      </label>

      <p v-if="isLongStory" class="hint">文本较长,解析可能较慢。</p>

      <footer>
        <button type="button" class="ghost-btn" @click="$router.back()">取消</button>
        <button
          type="button"
          class="ghost-btn"
          :disabled="!canSubmit || savingDraft || startingParse"
          @click="saveDraft"
        >
          {{ savingDraft ? "保存中..." : "保存草稿" }}
        </button>
        <button
          type="button"
          class="primary-btn"
          :disabled="!canSubmit || savingDraft || startingParse"
          @click="startParse"
        >
          {{ startingParse ? "启动中..." : "开始拆分分镜" }}
        </button>
      </footer>
    </form>
  </div>
</template>

<style scoped>
.create-form {
  max-width: 800px;
  margin: 24px auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: var(--panel-bg);
  padding: 32px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--panel-border);
}
.create-form label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.create-form input,
.create-form select,
.create-form textarea {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font: inherit;
}
.create-form footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}
.hint {
  font-size: 12px;
  color: var(--warning);
  margin: 0;
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
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
