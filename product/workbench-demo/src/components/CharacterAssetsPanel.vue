<script setup lang="ts">
import { storeToRefs } from "pinia";

import PanelSection from "@/components/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { currentProject, selectedCharacter, selectedCharacterId } = storeToRefs(store);
</script>

<template>
  <PanelSection kicker="角色设定页" title="所有角色列表与角色详情子页">
    <template #actions>
      <span class="tag accent">主角已锁定</span>
      <button class="ghost-btn" type="button">新增角色资产</button>
    </template>

    <div class="asset-browser">
      <div class="asset-list-panel">
        <div class="list-head">
          <strong>所有角色</strong>
          <span>{{ currentProject.characters.length }} 个资产</span>
        </div>
        <div class="asset-list">
          <button
            v-for="character in currentProject.characters"
            :key="character.id"
            class="asset-list-item"
            :class="{ active: selectedCharacterId === character.id }"
            type="button"
            @click="store.selectCharacter(character.id)"
          >
            <strong>{{ character.name }}</strong>
            <small>{{ character.summary }}</small>
          </button>
        </div>
      </div>

      <div class="asset-detail-panel" v-if="selectedCharacter">
        <div class="subpage-head">
          <div>
            <p class="panel-kicker">角色详情子页</p>
            <h3>{{ selectedCharacter.name }}</h3>
          </div>
          <span class="tag accent">{{ selectedCharacter.role }}</span>
        </div>

        <div class="asset-layout">
          <div class="reference-stage character-stage">
            <div class="reference-badge">角色参考图</div>
            <div class="silhouette"></div>
          </div>

          <div class="asset-info">
            <article class="asset-copy">
              <label>角色描述 string</label>
              <p>{{ selectedCharacter.description }}</p>
            </article>

            <article class="asset-meta">
              <span>视频形象参考</span>
              <ul>
                <li v-for="meta in selectedCharacter.meta" :key="meta">{{ meta }}</li>
              </ul>
            </article>
          </div>
        </div>
      </div>
    </div>
  </PanelSection>
</template>
