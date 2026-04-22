/* frontend/src/types/index.ts */
import type {
  CharacterRoleType,
  ProjectStageRaw,
  ProjectStageZh,
  SceneThemeRaw,
  StoryboardDetail
} from "./api";

export type RenderStatus = "success" | "processing" | "warning" | "failed";

/** 分镜卡片展示对象,对齐后端聚合接口与 StoryboardDetail(idx/duration_sec/scene_id 等字段)。 */
export interface StoryboardShot extends StoryboardDetail {}

export interface CharacterAsset {
  id: string;
  name: string;
  role: string; // 中文,aggregate 层已拼
  role_type?: CharacterRoleType; // aggregate M3a 会给;编辑时用
  is_protagonist: boolean; // M3a 新增
  locked: boolean; // M3a 新增
  summary: string | null;
  description: string | null;
  meta: string[];
  reference_image_url?: string | null; // M3a 新增
}

export interface SceneAsset {
  id: string;
  name: string;
  summary: string | null;
  usage: string;
  description: string | null;
  meta: string[];
  theme: SceneThemeRaw; // 后端裸字符串 palace/academy/harbor 或 null;CSS class 在组件内映射
  locked: boolean; // M3a 新增
  reference_image_url?: string | null; // M3a 新增
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
