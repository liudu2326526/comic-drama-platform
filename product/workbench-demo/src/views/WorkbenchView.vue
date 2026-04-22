<script setup lang="ts">
import { storeToRefs } from "pinia";

import SidebarProjects from "@/components/SidebarProjects.vue";
import ProjectSetupPanel from "@/components/ProjectSetupPanel.vue";
import StoryboardPanel from "@/components/StoryboardPanel.vue";
import CharacterAssetsPanel from "@/components/CharacterAssetsPanel.vue";
import SceneAssetsPanel from "@/components/SceneAssetsPanel.vue";
import GenerationPanel from "@/components/GenerationPanel.vue";
import ExportPanel from "@/components/ExportPanel.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { currentProject } = storeToRefs(store);
</script>

<template>
  <div class="page-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Comic Drama Platform</p>
        <h1>漫剧生成工作台 Demo</h1>
      </div>
      <div class="topbar-actions">
        <div class="status-pill">
          <span class="dot"></span>
          Mock Data Ready
        </div>
        <button class="ghost-btn" type="button">保存为产品原型</button>
      </div>
    </header>

    <main class="workspace-layout">
      <SidebarProjects />

      <section class="content-area">
        <nav class="workflow-nav">
          <button class="workflow-chip active" type="button">新建项目</button>
          <button class="workflow-chip" type="button">分镜工作台</button>
          <button class="workflow-chip" type="button">角色设定页</button>
          <button class="workflow-chip" type="button">场景设定页</button>
          <button class="workflow-chip" type="button">镜头生成页</button>
          <button class="workflow-chip" type="button">导出</button>
        </nav>

        <ProjectSetupPanel />
        <StoryboardPanel />
        <CharacterAssetsPanel />
        <SceneAssetsPanel />
        <GenerationPanel />
        <ExportPanel />

        <section class="overview-callout">
          <span>当前项目概览</span>
          <p>{{ currentProject.projectOverview }}</p>
        </section>
      </section>
    </main>
  </div>
</template>
