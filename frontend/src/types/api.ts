/* frontend/src/types/api.ts */
export interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

// 后端 spec §14 错误码
export const ERROR_CODE = {
  VALIDATION: 40001,
  STAGE_FORBIDDEN: 40301,
  NOT_FOUND: 40401,
  CONFLICT: 40901,
  RATE_LIMIT: 42901,
  INTERNAL: 50001,
  UPSTREAM: 50301
} as const;

export type ErrorCode = (typeof ERROR_CODE)[keyof typeof ERROR_CODE];

export type ProjectStageRaw =
  | "draft"
  | "storyboard_ready"
  | "characters_locked"
  | "scenes_locked"
  | "rendering"
  | "ready_for_export"
  | "exported";

export type ProjectStageZh =
  | "草稿中"
  | "分镜已生成"
  | "角色已锁定"
  | "场景已匹配"
  | "镜头生成中"
  | "待导出"
  | "已导出";

export interface ProjectSummary {
  id: string;
  name: string;
  stage: ProjectStageZh;
  stage_raw: ProjectStageRaw;
  genre: string | null;
  ratio: string;
  storyboard_count: number;
  character_count: number;
  scene_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: ProjectSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectCreateRequest {
  name: string;
  story: string;
  genre?: string | null;
  ratio?: string;
  setup_params?: string[] | null;
}

export interface ProjectCreateResponse {
  id: string;
  stage: ProjectStageRaw;
  created_at: string;
}

export interface ProjectUpdateRequest {
  name?: string;
  genre?: string | null;
  ratio?: string;
  setup_params?: string[] | null;
}

export interface ProjectRollbackRequest {
  to_stage: ProjectStageRaw;
}

export interface ProjectRollbackResponse {
  from_stage: ProjectStageRaw;
  to_stage: ProjectStageRaw;
  invalidated: {
    shots_reset: number;
    characters_unlocked: number;
    scenes_unlocked: number;
  };
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export interface JobState {
  id: string;
  kind: string;
  status: JobStatus;
  progress: number;
  total: number | null;
  done: number;
  result: unknown | null;
  error_msg: string | null;
  created_at: string;
  finished_at: string | null;
}

// ---- M2: storyboards / parse ----
export interface StoryboardDetail {
  id: string;
  idx: number;
  title: string;
  description: string;
  detail: string | null;
  duration_sec: number | null;
  tags: string[] | null;
  status: string; // pending|generating|succeeded|failed|locked
  scene_id: string | null;
  current_render_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryboardCreateRequest {
  title?: string; // ≤ 128
  description?: string;
  detail?: string | null;
  duration_sec?: number | null; // 0 ≤ x ≤ 300
  tags?: string[] | null;
  idx?: number | null; // 1..999;null/缺省 = 追加到尾
}

export interface StoryboardUpdateRequest {
  title?: string; // ≤ 128;显式 null 会被后端 422
  description?: string;
  detail?: string | null; // 显式 null 允许(清空)
  duration_sec?: number;
  tags?: string[];
}

export interface StoryboardReorderRequest {
  ordered_ids: string[]; // 必须正好包含当前项目下全部分镜 id
}

export interface StoryboardReorderResponse {
  reordered: number;
}

export interface StoryboardConfirmResponse {
  stage: ProjectStageRaw;
  stage_raw: ProjectStageRaw;
}

export interface StoryboardDeleteResponse {
  deleted: boolean;
}

export interface ProjectParseResponse {
  job_id: string;
}
