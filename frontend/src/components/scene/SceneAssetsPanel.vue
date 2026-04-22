<!-- frontend/src/components/scene/SceneAssetsPanel.vue -->
<script setup lang="ts">
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { current, selectedScene, selectedSceneId } = storeToRefs(store);
</script>

<template>
  <PanelSection v-if="current" kicker="04" title="场景设定">
    <template #actions>
      <button class="ghost-btn" type="button" disabled>新增场景资产</button>
    </template>

    <div v-if="!current.scenes.length" class="empty-note">
      尚未生成场景 · 角色锁定后将自动匹配场景
    </div>
    <div v-else class="asset-browser">
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
            <strong>{{ scene.name }}</strong>
            <small>{{ scene.summary }}</small>
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
          <div class="reference-stage scene-stage" :class="selectedScene.theme">
            <div class="reference-badge">场景参考图</div>
            <div class="scene-layers">
              <span class="moon" />
              <span class="wall" />
              <span class="well" />
            </div>
          </div>

          <div class="asset-info">
            <article class="asset-copy">
              <label>场景描述</label>
              <p>{{ selectedScene.description }}</p>
            </article>

            <article class="asset-meta">
              <span>视觉风格参考</span>
              <ul>
                <li v-for="meta in selectedScene.meta" :key="meta">{{ meta }}</li>
              </ul>
            </article>
          </div>
        </div>
      </div>
    </div>
  </PanelSection>
</template>

<style scoped>
.asset-browser {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 20px;
}
.asset-list-panel {
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.list-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.list-head strong {
  font-size: 15px;
}
.list-head span {
  font-size: 12px;
  color: var(--text-faint);
}
.asset-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.asset-list-item {
  width: 100%;
  padding: 14px;
  text-align: left;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 160ms;
}
.asset-list-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.asset-list-item.active {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.asset-list-item strong {
  display: block;
  font-size: 14px;
  margin-bottom: 4px;
}
.asset-list-item small {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}
.asset-detail-panel {
  padding: 24px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-md);
}
.subpage-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.subpage-head h3 {
  margin: 0;
  font-size: 22px;
}
.asset-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 24px;
}
.reference-stage {
  position: relative;
  min-height: 280px;
  border-radius: var(--radius-md);
  background: #0b0d1a;
  border: 1px solid var(--panel-border);
  overflow: hidden;
}
.reference-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: 10px;
  border-radius: 4px;
}
.scene-layers {
  position: absolute;
  inset: 0;
}
.moon {
  position: absolute;
  top: 40px;
  right: 40px;
  width: 60px;
  height: 60px;
  background: radial-gradient(circle, #fff, transparent);
  border-radius: 50%;
  opacity: 0.8;
}
.wall {
  position: absolute;
  bottom: 40px;
  left: 20px;
  right: 20px;
  height: 100px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
}
.well {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 80px;
  height: 40px;
  background: rgba(255, 255, 255, 0.05);
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-radius: 40px 40px 0 0;
}
.asset-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.asset-copy label {
  display: block;
  font-size: 12px;
  color: var(--accent);
  margin-bottom: 8px;
}
.asset-copy p {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.6;
}
.asset-meta span {
  display: block;
  font-size: 12px;
  color: var(--text-faint);
  margin-bottom: 10px;
}
.asset-meta ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
}
.tag {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
}
.empty-note {
  padding: 40px 0;
  text-align: center;
  color: var(--text-faint);
  font-size: 14px;
}
</style>
