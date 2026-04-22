/* frontend/src/types/index.ts */
import type { ProjectStageRaw, ProjectStageZh, StoryboardDetail } from "./api";

export type RenderStatus = "success" | "processing" | "warning" | "failed";
export type SceneTheme = "theme-palace" | "theme-academy" | "theme-harbor";

/** 分镜卡片展示对象, 对齐后端聚合接口与 StoryboardDetail */
export interface StoryboardShot extends StoryboardDetail {}

export interface CharacterAsset {
  id: string;
  name: string;
  role: string;
  summary: string;
  description: string;
  meta: string[];
}

export interface SceneAsset {
  id: string;
  name: string;
  summary: string;
  usage: string;
  description: string;
  meta: string[];
  theme: SceneTheme;
}

export interface RenderQueueItem {
  id: string;
  title: string;
  summary: string;
  status: RenderStatus;
}

export interface ExportTask {
  id: string;
  name: string;
  summary: string;
  status: RenderStatus;
  progressLabel: string;
}

export interface ProjectData {
  id: string;
  name: string;
  stage: ProjectStageZh;
  stage_raw: ProjectStageRaw;
  genre: string | null;
  ratio: string;
  suggestedShots: string;
  story: string;
  summary: string;
  parsedStats: string[];
  setupParams: string[];
  projectOverview: string;
  storyboards: StoryboardShot[];
  characters: CharacterAsset[];
  scenes: SceneAsset[];
  generationProgress: string;
  generationNotes: { input: string; suggestion: string };
  generationQueue: RenderQueueItem[];
  exportConfig: string[];
  exportDuration: string;
  exportTasks: ExportTask[];
}
