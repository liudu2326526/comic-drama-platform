<script setup lang="ts">
import { storeToRefs } from "pinia";

import PanelSection from "@/components/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { currentProject, selectedScene, selectedSceneId } = storeToRefs(store);
</script>

<template>
  <PanelSection kicker="场景设定页" title="所有场景列表与场景详情子页">
    <template #actions>
      <span v-if="selectedScene" class="tag">{{ selectedScene.usage }}</span>
      <button class="ghost-btn" type="button">新增场景资产</button>
    </template>

    <div class="asset-browser">
      <div class="asset-list-panel">
        <div class="list-head">
          <strong>所有场景</strong>
          <span>{{ currentProject.scenes.length }} 个资产</span>
        </div>
        <div class="asset-list">
          <button
            v-for="scene in currentProject.scenes"
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

      <div class="asset-detail-panel" v-if="selectedScene">
        <div class="subpage-head">
          <div>
            <p class="panel-kicker">场景详情子页</p>
            <h3>{{ selectedScene.name }}</h3>
          </div>
          <span class="tag">{{ selectedScene.usage }}</span>
        </div>

        <div class="asset-layout">
          <div class="reference-stage scene-stage" :class="selectedScene.theme">
            <div class="reference-badge">场景参考图</div>
            <div class="scene-layers">
              <span class="moon"></span>
              <span class="wall"></span>
              <span class="well"></span>
            </div>
          </div>

          <div class="asset-info">
            <article class="asset-copy">
              <label>场景描述 string</label>
              <p>{{ selectedScene.description }}</p>
            </article>

            <article class="asset-meta">
              <span>视频形象参考</span>
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
