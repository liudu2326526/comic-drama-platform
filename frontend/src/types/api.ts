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
  CONTENT_FILTER: 42201, // ← 新增(M3a)
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
  | "角色设定中"
  | "场景设定中"
  | "镜头待生成"
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

export type PromptProfileKind = "character" | "scene";
export type PromptProfileStatus = "empty" | "draft_only" | "applied" | "dirty";

export interface PromptProfilePayload {
  prompt: string;
  source: "ai" | "manual";
}

export interface PromptProfileState {
  draft: PromptProfilePayload | null;
  applied: PromptProfilePayload | null;
  status: PromptProfileStatus;
}

export type StyleReferenceKind = "character" | "scene";
export type StyleReferenceStatus = "empty" | "running" | "succeeded" | "failed";

export interface StyleReferenceState {
  imageUrl: string | null;
  prompt: string | null;
  status: StyleReferenceStatus;
  error: string | null;
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export interface JobResultPayload {
  next_job_id?: string | null;
  next_kind?: "gen_character_asset" | null;
  character_ids?: string[];
  render_id?: string | null;
  draft_id?: string | null;
  version_no?: number | null;
}

export interface JobState {
  id: string;
  kind: string;
  status: JobStatus;
  progress: number;
  display_progress?: number;
  elapsed_seconds?: number;
  estimated_total_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  estimated_source?: string | null;
  total: number | null;
  done: number;
  payload: unknown | null;
  result: JobResultPayload | null;
  error_msg: string | null;
  target_type?: string | null;
  target_id?: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface RenderDraftReference {
  id: string;
  kind: string;
  source_id: string;
  name: string;
  alias?: string;
  mention_key?: string;
  image_url: string;
  origin?: ReferenceOrigin;
  reason: string;
}

export type ReferenceOrigin = "auto" | "manual" | "history";

export interface ReferenceCandidate {
  id: string;
  kind: string;
  source_id: string;
  name: string;
  alias: string;
  mention_key: string;
  image_url: string;
  origin: ReferenceOrigin;
  reason: string | null;
}

export interface ReferenceAssetCreate {
  name: string;
  image_url: string;
  kind?: "manual";
}

export interface ReferenceMention {
  mention_key: string;
  label: string;
}

export interface RenderDraftRead {
  id?: string;
  shot_id: string;
  version_no?: number;
  prompt: string;
  references: RenderDraftReference[];
  optimizer_snapshot?: Record<string, unknown> | null;
  created_at?: string;
}

export interface RenderSubmitReference {
  id: string;
  kind: string;
  source_id: string;
  name: string;
  image_url: string;
  alias?: string | null;
  mention_key?: string | null;
  origin?: string | null;
}

export interface RenderSubmitRequest {
  prompt: string;
  references: RenderSubmitReference[];
  reference_mentions?: ReferenceMention[];
}

export const SHOT_VIDEO_DURATION_PRESETS = [4, 5, 8, 10] as const;
export type ShotVideoDurationPreset = (typeof SHOT_VIDEO_DURATION_PRESETS)[number];
export type ShotVideoResolution = "480p" | "720p";
export type ShotVideoModelType = "standard" | "fast";

export interface ShotVideoSubmitRequest {
  prompt: string;
  references: RenderSubmitReference[];
  reference_mentions?: ReferenceMention[];
  duration?: number;
  resolution: ShotVideoResolution;
  model_type: ShotVideoModelType;
}

export interface ShotVideoVersionRead {
  id: string;
  shot_id: string;
  version_no: number;
  status: string;
  prompt_snapshot: Record<string, unknown> | null;
  params_snapshot: Record<string, unknown> | null;
  video_url: string | null;
  last_frame_url: string | null;
  provider_task_id: string | null;
  error_code: string | null;
  error_msg: string | null;
  created_at: string;
  finished_at: string | null;
  is_current: boolean;
}

export interface ShotVideoVersionSelectResponse {
  shot_id: string;
  current_video_render_id: string | null;
  status: string;
}

export interface RenderVersionRead {
  id: string;
  shot_id: string;
  version_no: number;
  status: string;
  prompt_snapshot: Record<string, unknown> | null;
  image_url: string | null;
  provider_task_id: string | null;
  error_code: string | null;
  error_msg: string | null;
  created_at: string;
  finished_at: string | null;
  is_current: boolean;
}

export interface RenderVersionSelectResponse {
  shot_id: string;
  current_render_id: string | null;
  status: string;
}

export interface ShotLockResponse {
  shot_id: string;
  current_video_render_id: string | null;
  status: string;
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
  source_excerpt?: string | null;
  source_anchor?: Record<string, unknown> | null;
  beats?: Array<Record<string, unknown>> | null;
  status: string; // pending|generating|succeeded|failed|locked
  scene_id: string | null;
  current_render_id: string | null;
  current_video_render_id?: string | null;
  current_video_url?: string | null;
  current_last_frame_url?: string | null;
  current_video_version_no?: number | null;
  current_video_params_snapshot?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface StoryboardCreateRequest {
  title?: string; // ≤ 128
  description?: string;
  detail?: string | null;
  duration_sec?: number | null; // 0 ≤ x ≤ 300
  tags?: string[] | null;
  source_excerpt?: string | null;
  source_anchor?: Record<string, unknown> | null;
  beats?: Array<Record<string, unknown>> | null;
  idx?: number | null; // 1..999;null/缺省 = 追加到尾
}

export interface StoryboardUpdateRequest {
  title?: string; // ≤ 128;显式 null 会被后端 422
  description?: string;
  detail?: string | null; // 显式 null 允许(清空)
  duration_sec?: number;
  tags?: string[];
  source_excerpt?: string;
  source_anchor?: Record<string, unknown>;
  beats?: Array<Record<string, unknown>>;
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

export interface WorkflowStageConfirmResponse {
  stage: ProjectStageRaw;
  stage_raw: ProjectStageRaw;
}

export interface StoryboardDeleteResponse {
  deleted: boolean;
}

export interface ProjectParseResponse {
  job_id: string;
}

// ---- M3a: characters / scenes / bind_scene ----
export type CharacterRoleType = "protagonist" | "supporting" | "atmosphere";

export interface CharacterOut {
  id: string;
  name: string;
  role: string; // 中文展示值 "主角"/"配角"/"氛围",与后端 role_map 一致
  role_type: CharacterRoleType; // 原始 ENUM,编辑弹窗下拉用
  is_protagonist: boolean;
  locked: boolean;
  summary: string | null;
  description: string | null;
  meta: string[]; // 后端已格式化;含 "人像库:Active" 等 tag
  reference_image_url: string | null; // aggregate 层拼好的 OBS 公网 URL
}

export interface CharacterUpdate {
  name?: string; // min 1, max 64;显式 null 会被后端 422
  summary?: string | null;
  description?: string | null;
  meta?: Record<string, unknown> | null;
  role_type?: CharacterRoleType; // 不允许显式 null
}

export interface CharacterGenerateRequest {
  extra_hints?: string[]; // 允许为空;后端 M3a 暂不消费,保留给后续 prompt 增强
}

export interface GenerateJobAck {
  job_id: string; // 主 job;前端只轮询它
  sub_job_ids: string[]; // 子 job 列表,本期只用于调试打印
}

export type SceneThemeRaw = "palace" | "academy" | "harbor" | string | null;

export interface SceneOut {
  id: string;
  name: string;
  theme: SceneThemeRaw;
  locked: boolean;
  summary: string | null;
  description: string | null;
  meta: string[];
  usage: string; // "场景复用 N 镜头"
  template_id: string | null;
  reference_image_url: string | null;
}

export interface SceneUpdate {
  name?: string;
  theme?: string;
  summary?: string | null;
  description?: string | null;
  meta?: Record<string, unknown> | null;
  template_id?: string | null;
}

export interface SceneGenerateRequest {
  template_whitelist?: string[]; // 空 = 不限;后端 M3a 暂不消费,保留给后续模板筛选
}

export interface BindSceneRequest {
  scene_id: string;
}

export interface BindSceneResponse {
  shot_id: string;
  scene_id: string;
  scene_name: string;
}
