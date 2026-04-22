import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { mockProjects } from "@/mock/projects";

export const useWorkbenchStore = defineStore("workbench", () => {
  const projects = ref(mockProjects);
  const currentProjectId = ref(projects.value[0]?.id ?? "");
  const selectedCharacterId = ref(projects.value[0]?.characters[0]?.id ?? "");
  const selectedSceneId = ref(projects.value[0]?.scenes[0]?.id ?? "");

  const currentProject = computed(
    () => projects.value.find((project) => project.id === currentProjectId.value) ?? projects.value[0]
  );

  const selectedShotId = ref(currentProject.value?.storyboards[0]?.id ?? "");

  const currentShot = computed(
    () => currentProject.value.storyboards.find((shot) => shot.id === selectedShotId.value) ?? currentProject.value.storyboards[0]
  );

  const selectedCharacter = computed(
    () =>
      currentProject.value.characters.find((character) => character.id === selectedCharacterId.value) ??
      currentProject.value.characters[0]
  );

  const selectedScene = computed(
    () => currentProject.value.scenes.find((scene) => scene.id === selectedSceneId.value) ?? currentProject.value.scenes[0]
  );

  const sidebarMetrics = computed(() => {
    const exportQueue = projects.value.flatMap((project) => project.exportTasks).filter((task) => task.status === "processing")
      .length;

    return [
      { label: "今日产出", value: `${projects.value.length} 个项目` },
      { label: "镜头通过率", value: "91%" },
      { label: "导出队列", value: `${exportQueue} 个任务` }
    ];
  });

  function resetProjectSelection() {
    selectedCharacterId.value = currentProject.value.characters[0]?.id ?? "";
    selectedSceneId.value = currentProject.value.scenes[0]?.id ?? "";
    selectedShotId.value = currentProject.value.storyboards[0]?.id ?? "";
  }

  function selectProject(projectId: string) {
    currentProjectId.value = projectId;
    resetProjectSelection();
  }

  function selectCharacter(characterId: string) {
    selectedCharacterId.value = characterId;
  }

  function selectScene(sceneId: string) {
    selectedSceneId.value = sceneId;
  }

  function selectShot(shotId: string) {
    selectedShotId.value = shotId;
  }

  return {
    projects,
    currentProject,
    currentShot,
    selectedCharacter,
    selectedScene,
    sidebarMetrics,
    currentProjectId,
    selectedCharacterId,
    selectedSceneId,
    selectedShotId,
    selectProject,
    selectCharacter,
    selectScene,
    selectShot
  };
});
