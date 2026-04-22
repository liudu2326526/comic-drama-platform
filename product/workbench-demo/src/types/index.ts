export type ProjectStage = "分镜确认中" | "角色已锁定" | "待导出";
export type RenderStatus = "success" | "processing" | "warning";
export type SceneTheme = "theme-palace" | "theme-academy" | "theme-harbor";

export interface StoryboardShot {
  id: string;
  index: number;
  title: string;
  description: string;
  detail: string;
  duration: string;
  tags: string[];
}

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
  stage: ProjectStage;
  genre: string;
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
  generationNotes: {
    input: string;
    suggestion: string;
  };
  generationQueue: RenderQueueItem[];
  exportConfig: string[];
  exportDuration: string;
  exportTasks: ExportTask[];
}
