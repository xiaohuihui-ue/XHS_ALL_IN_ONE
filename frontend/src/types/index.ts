export type PlatformId = "xhs" | "douyin" | "kuaishou" | "weibo" | "xianyu" | "taobao";

export type PlatformMeta = {
  id: PlatformId;
  name_cn: string;
  name_en: string;
  enabled: boolean;
  status: "enabled" | "coming_soon";
  accent_color: string;
  icon: string;
};

export type Paginated<T> = {
  total: number;
  page: number;
  page_size: number;
  items: T[];
};

export type DashboardOverview = {
  platform: "xhs";
  today_crawls: number;
  saved_notes: number;
  pending_publishes: number;
  healthy_accounts: number;
  at_risk_accounts: number;
  comment_count?: number;
  total_engagement?: number;
  hot_topics: Array<{ keyword: string; notes: number; engagement: number }>;
  recent_activity: Array<{ type: string; title: string; status: string }>;
};

export type PlatformUser = {
  id: number;
  username: string;
};

export type AuthTokens = {
  access_token: string;
  refresh_token?: string;
  token_type: "bearer";
};

export type AuthPayload = AuthTokens & {
  user: PlatformUser;
};

export type PlatformAccount = {
  id: number;
  platform: PlatformId;
  sub_type: "pc" | "creator" | null;
  external_user_id?: string;
  nickname: string;
  avatar_url?: string;
  status: "active" | "healthy" | "expired" | "risk" | "unknown" | string;
  status_message?: string;
  profile?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  action?: "created" | "updated" | string;
};

export type XhsQrLoginSession = {
  session_id: number;
  status: "pending" | "scanned" | "confirmed" | "expired" | string;
  qr_url: string;
  qr_image_data_url?: string;
  account?: PlatformAccount | null;
};

export type XhsSearchNote = {
  note_id: string;
  note_url?: string;
  title: string;
  content: string;
  author_id: string;
  author_name: string;
  author_avatar: string;
  cover_url: string;
  likes: number;
  collects: number;
  comments: number;
  shares: number;
  type: string;
  timestamp?: number | string;
  image_urls?: string[];
  video_url?: string;
  video_addr?: string;
  tags?: string[];
  raw: Record<string, unknown>;
};

export type XhsNoteSearchResponse = {
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  items: XhsSearchNote[];
  raw: Record<string, unknown>;
};

export type XhsSearchOptions = {
  account_id: number;
  keyword: string;
  page?: number;
  sort_type_choice?: number;
  note_type?: number;
  note_time?: number;
  note_range?: number;
  pos_distance?: number;
  geo?: string;
};

export type XhsDataCrawlMode = "note_urls" | "search" | "comments";

export type XhsDataCrawlPayload = {
  account_id: number;
  mode: XhsDataCrawlMode;
  urls?: string[];
  keyword?: string;
  pages?: number;
  max_notes?: number;
  time_sleep?: number;
  fetch_comments?: boolean;
  sort_type_choice?: number;
  note_type?: number;
  note_time?: number;
  note_range?: number;
  pos_distance?: number;
  geo?: string;
};

export type XhsDataCrawlItem = {
  source: string;
  status: "success" | "failed" | string;
  error: string;
  note?: XhsSearchNote | null;
  comments: NoteComment[];
  comment_count: number;
};

export type XhsDataCrawlResponse = {
  task: TaskRecord;
  total: number;
  success_count: number;
  failed_count: number;
  items: XhsDataCrawlItem[];
};

export type SavedNote = {
  id: number;
  platform: PlatformId;
  platform_account_id: number;
  note_id: string;
  title: string;
  content: string;
  author_name: string;
  raw_json?: Record<string, unknown>;
  asset_urls?: string[];
  cover_url?: string;
  video_url?: string;
  video_addr?: string;
  created_at: string;
  tags?: Tag[];
};

export type AnalyticsTopContent = {
  id: number;
  note_id: string;
  title: string;
  author_name: string;
  created_at: string;
  likes: number;
  collects: number;
  comments: number;
  shares: number;
  engagement: number;
};

export type AnalyticsHotTopic = {
  keyword: string;
  notes: number;
  engagement: number;
};

export type AnalyticsCommentInsight = {
  total_comments: number;
  question_count: number;
  top_terms: Array<{ term: string; count: number }>;
  top_comments: Array<{
    id: number;
    note_id: number;
    user_name: string;
    content: string;
    like_count: number;
  }>;
};

export type BenchmarkTopNote = AnalyticsTopContent;

export type BenchmarkItem = {
  target_id: number;
  target_type: "account" | "brand" | string;
  name: string;
  value: string;
  status: string;
  last_refreshed_at?: string | null;
  matched_notes: number;
  total_engagement: number;
  average_engagement: number;
  top_notes: BenchmarkTopNote[];
};

export type BenchmarkOverview = {
  total_targets: number;
  matched_notes: number;
  total_engagement: number;
  average_engagement: number;
  items: BenchmarkItem[];
};

export type NoteAsset = {
  id: number;
  note_id: number;
  asset_type: "image" | "video" | string;
  url: string;
  local_path: string;
  download_url?: string;
  sort_order?: number;
};

export type NoteComment = {
  id: number;
  note_id: number;
  comment_id: string;
  user_name: string;
  user_id?: string | null;
  content: string;
  like_count: number;
  parent_comment_id?: string | null;
  created_at_remote?: string | null;
  raw_json?: Record<string, unknown>;
};

export type Tag = {
  id: number;
  name: string;
  color: string;
};

export type TagPayload = {
  name: string;
  color?: string;
};

export type BatchTagNotesPayload = {
  note_ids: number[];
  tag_ids: number[];
  mode: "replace" | "add" | "remove";
};

export type BatchTagNotesResponse = {
  updated_count: number;
  items: SavedNote[];
};

export type BatchCreateDraftsPayload = {
  note_ids: number[];
  intent?: "rewrite" | "publish" | string;
};

export type BatchCreateDraftsResponse = {
  created_count: number;
  items: Draft[];
};

export type BenchmarkCreateDraftsResponse = BatchCreateDraftsResponse;

export type NotesExportPayload = {
  note_ids: number[];
  format?: "json" | "csv";
};

export type NotesExportResponse = {
  exported_count: number;
  file_name: string;
  file_path: string;
  download_url: string;
};

export type AnalyticsReportPayload = {
  note_ids?: number[];
  format?: "json";
};

export type AnalyticsReportResponse = {
  report_type: "operations";
  generated_at: string;
  note_count: number;
  file_name: string;
  file_path: string;
  download_url: string;
  summary: {
    note_count: number;
    total_engagement: number;
    comment_count: number;
    top_topics: AnalyticsHotTopic[];
    top_notes: AnalyticsTopContent[];
    benchmark_count: number;
  };
};

export type SaveNotesResponse = {
  saved_count: number;
  items: SavedNote[];
};

export type Draft = {
  id: number;
  platform: PlatformId;
  title: string;
  body: string;
  tags?: { id?: string; name: string }[];
  source_note_id?: number | null;
  created_at: string;
};

export type CreateDraftPayload = {
  platform: "xhs";
  source_note_id?: number;
  title?: string;
  body?: string;
  intent?: "rewrite" | "publish" | string;
};

export type ModelType = "text" | "image";
export type ModelCapability = "text_generation" | "vision" | "image_generation" | "image_edit";

export type ModelConfig = {
  id: number;
  name: string;
  model_type: ModelType;
  provider: string;
  model_name: string;
  base_url: string;
  has_api_key: boolean;
  is_default: boolean;
  capabilities: ModelCapability[];
};

export type ModelConfigPayload = {
  name: string;
  model_type: ModelType;
  provider: string;
  model_name: string;
  base_url: string;
  api_key: string;
  is_default: boolean;
  capabilities: ModelCapability[];
};

export type ModelConfigBackup = {
  version: 1;
  configs: ModelConfigPayload[];
};

export type ModelConfigImportResult = {
  imported_count: number;
  created_count: number;
  updated_count: number;
  items: ModelConfig[];
};

export type RewriteDraftPayload = {
  draft_id: number;
  instruction?: string;
};

export type GenerateNotePayload = {
  platform?: "xhs";
  topic: string;
  reference?: string;
  instruction?: string;
};

export type GenerateTitlePayload = {
  title?: string;
  body: string;
  count?: number;
};

export type GenerateTagsPayload = {
  title?: string;
  body: string;
  count?: number;
};

export type PolishTextPayload = {
  text: string;
  instruction?: string;
};

export type GeneratedImageAsset = {
  id: number;
  draft_id?: number | null;
  prompt: string;
  model_name: string;
  params: Record<string, unknown>;
  file_path: string;
  created_at: string;
};

export type GenerateCoverPayload = {
  prompt: string;
  draft_id?: number;
  size?: string;
  style?: string;
};

export type GenerateImagePayload = {
  prompt: string;
  reference_images?: string[];
  size?: string;
  quality?: string;
  style?: string;
  response_format?: string;
  save_to_assets?: boolean;
};

export type GenerateImageResult = {
  url: string;
  raw?: unknown;
  asset?: GeneratedImageAsset;
};

export type UserImageFile = {
  file_name: string;
  url: string;
  size: number;
};

export type DescribeImagePayload = {
  image_url: string;
  instruction?: string;
};

export type ImageUtilityFile = {
  file_name: string;
  file_path: string;
  download_url: string;
  width: number;
  height: number;
  media_type: string;
};

export type ComposeImagePayload = {
  title: string;
  body?: string;
  width?: number;
  height?: number;
  background_color?: string;
  accent_color?: string;
};

export type ResizeImagePayload = {
  source_file_name: string;
  width?: number;
  height?: number;
  mode?: "cover" | "contain";
  format?: "png" | "jpeg";
  quality?: number;
};

export type TaskRecord = {
  id: number;
  platform: PlatformId;
  task_type: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled" | "exhausted" | string;
  progress: number;
  payload: Record<string, unknown>;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  error_type?: string | null;
  retry_count?: number;
  max_retries?: number;
  parent_task_id?: number | null;
  children?: TaskRecord[];
};

export type SchedulerStatus = {
  enabled: boolean;
  running: boolean;
  interval_seconds: number;
  jobs: Array<{
    id: string;
    next_run_time?: string | null;
  }>;
  recent_tasks: TaskRecord[];
};

export type RunDueTasksResponse = {
  executed_count: number;
  failed_count: number;
  items: PublishJob[];
};

export type MonitoringTarget = {
  id: number;
  platform: PlatformId;
  target_type: "keyword" | "account" | "brand" | "note_url" | string;
  name: string;
  value: string;
  status: "active" | "paused" | string;
  config: Record<string, unknown>;
  last_refreshed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type MonitoringTargetPayload = {
  target_type: "keyword" | "account" | "brand" | "note_url";
  name?: string;
  value: string;
  status?: "active" | "paused";
  config?: Record<string, unknown>;
};

export type MonitoringSnapshot = {
  id: number;
  target_id: number;
  payload: {
    matched_count?: number;
    total_engagement?: number;
    top_notes?: Array<{
      id: number;
      note_id: string;
      title: string;
      author_name: string;
      engagement: number;
    }>;
  };
  created_at: string;
};

export type MonitoringNote = {
  id: number;
  note_id: string;
  title: string;
  author_name: string;
  created_at: string;
  likes: number;
  collects: number;
  comments: number;
  shares: number;
  engagement: number;
};

export type MonitoringRefreshResponse = {
  target: MonitoringTarget;
  task: TaskRecord;
  snapshot: MonitoringSnapshot;
};

export type KeywordGroup = {
  id: number;
  platform: PlatformId;
  name: string;
  keywords: string[];
  created_at: string;
  updated_at: string;
};

export type KeywordGroupPayload = {
  platform?: PlatformId;
  name: string;
  keywords: string[];
};

export type KeywordGroupDetail = KeywordGroup & {
  trend: {
    total_matches: number;
    total_engagement: number;
    keywords: Array<{ keyword: string; notes: number; engagement: number }>;
    matched_notes: Array<{
      id: number;
      note_id: string;
      title: string;
      author_name: string;
      engagement: number;
      created_at: string;
    }>;
  };
};

export type PublishJob = {
  id: number;
  platform_account_id: number;
  source_draft_id?: number | null;
  platform: PlatformId;
  title: string;
  body: string;
  publish_mode: "immediate" | "scheduled" | string;
  publish_options?: PublishOptions;
  status: "pending" | "uploading" | "publishing" | "scheduled" | "published" | "failed" | "cancelled" | string;
  scheduled_at?: string | null;
  external_note_id: string;
  publish_error: string;
  published_at?: string | null;
  created_at: string;
};

export type PublishOptions = {
  topics?: string[];
  location?: string;
  privacy_type?: 0 | 1 | number;
  is_private?: boolean;
  draft_tags?: Array<{ id?: string; name?: string }>;
};

export type SendDraftToPublishPayload = {
  platform_account_id?: number | null;
  publish_mode?: "immediate" | "scheduled";
  scheduled_at?: string | null;
  topics?: string[];
  location?: string | null;
  privacy_type?: 0 | 1 | null;
  is_private?: boolean | null;
};

export type PublishJobUpdatePayload = {
  title?: string;
  body?: string;
  platform_account_id?: number | null;
  publish_mode?: "immediate" | "scheduled";
  scheduled_at?: string | null;
  topics?: string[];
  location?: string | null;
  privacy_type?: 0 | 1 | null;
  is_private?: boolean | null;
};

export type PublishAsset = {
  id: number;
  publish_job_id: number;
  asset_type: "image" | "video" | string;
  file_path: string;
  upload_status: "pending" | "uploading" | "uploaded" | "failed" | string;
  creator_media_id: string;
  upload_error: string;
  creator_upload_info: Record<string, unknown>;
};

export type PublishAssetPayload = {
  asset_type: "image" | "video";
  file_path: string;
};

export type AutoTask = {
  id: number;
  user_id: number;
  name: string;
  keywords: string[];
  pc_account_id: number;
  creator_account_id: number;
  ai_instruction: string;
  status: "active" | "paused" | "completed" | string;
  last_run_at?: string | null;
  next_run_at?: string | null;
  total_published: number;
  created_at: string;
  schedule_type: "manual" | "daily" | "weekly" | "interval";
  schedule_time: string;
  schedule_days: string;
  schedule_interval_hours: number;
};

export type AutoTaskCreatePayload = {
  name: string;
  keywords: string[];
  pc_account_id: number;
  creator_account_id: number;
  ai_instruction?: string;
  schedule_type?: "manual" | "daily" | "weekly" | "interval";
  schedule_time?: string;
  schedule_days?: string;
  schedule_interval_hours?: number;
};

export type AutoTaskUpdatePayload = {
  name?: string;
  keywords?: string[];
  ai_instruction?: string;
  status?: "active" | "paused" | "completed";
  schedule_type?: "manual" | "daily" | "weekly" | "interval";
  schedule_time?: string;
  schedule_days?: string;
  schedule_interval_hours?: number;
};

export type AutoTaskRunResult = {
  auto_task: AutoTask;
  keyword: string;
  source_note: {
    note_id: string;
    title: string;
    likes: number;
    collects: number;
    comments: number;
  };
  draft: {
    id: number;
    title: string;
    body: string;
    created_at: string;
  };
  publish_job: {
    id: number;
    status: string;
    platform_account_id: number;
  };
};

export type AppNotification = {
  id: number;
  title: string;
  body: string;
  level: "info" | "warning" | "error" | string;
  source_task_id?: number | null;
  source_type?: string | null;
  source_id?: number | null;
  read: boolean;
  created_at: string;
};

export interface AgentDraftRequestMessage {
  role: "system" | "user" | "assistant";
  content:
    | string
    | Array<
        | { type: "text"; text: string }
        | { type: "image_url"; image_url: { url: string } }
      >;
}

export interface AgentResearchOptions {
  keywords?: string[];
  reference_note_ids?: number[];
  search_account_id?: number | null;
  search_limit?: number;
  auto_save?: boolean;
}

export interface AgentDraftPayload {
  model?: string;
  messages: AgentDraftRequestMessage[];
  n?: number;
  temperature?: number;
  top_p?: number;
  stream?: false;
  response_format?: {
    type: "json_schema";
    json_schema: {
      name: string;
      strict: boolean;
      schema: Record<string, unknown>;
    };
  };
  metadata?: {
    platform: "xhs";
    account_id?: number | null;
    save_to_drafts?: string;
    output_requirements?: string;
    research?: AgentResearchOptions;
  };
  image_options?: {
    model?: string;
    n?: number;
    size?: string;
    quality?: string;
    style?: string;
    response_format?: string;
  };
  user?: string;
  // step-mode fields
  step?: "titles" | "draft" | "images";
  selected_title?: string;
  draft_id?: number;
  image_prompt?: string;
  // step=images fields
  cover_strategy?: CoverStrategy;
  image_prompt_spec?: ImagePromptSpec;
  draft_body?: string;
  reference_image_urls?: string[];
}

export interface AgentDraftItem {
  draft: {
    id: number;
    platform: string;
    title: string;
    body: string;
    tags: Array<{ name: string }>;
    created_at: string;
  };
  image_prompt?: {
    positive_prompt: string;
    negative_prompt: string;
    reference_strategy: string;
  };
  assets: Array<{
    id: number;
    draft_id: number;
    asset_type: string;
    url: string;
    local_path: string;
    sort_order: number;
  }>;
  status: "completed" | "partial" | "failed";
  errors: string[];
  // Extended fields
  cover_strategy?: CoverStrategy;
  image_prompt_spec?: ImagePromptSpec;
  publish_tips?: string;
  final_image_prompt?: string;
  iteration_history?: IterationRound[];
  image_quality_check?: ImageQualityCheck;
  quality_check?: ImageQualityCheck;
}

export interface CoverStrategy {
  cover_goal: string;
  cover_type: string;
  visual_core: string;
  title_space: string;
  text_in_image: boolean;
}

export interface ImagePromptSpec {
  L1_publish_goal: string;
  L2_topic: string;
  L3_audience: string;
  L4_main_subject: string;
  L5_scene: string;
  L6_composition: string;
  L7_style: string;
  L8_color_lighting: string;
  L9_emotion: string;
  L10_details: string;
  L11_platform_adaptation: string;
  L12_negative_constraints: string;
}

export interface PromptQualityScore {
  theme_clarity: number;
  subject_clarity: number;
  composition_control: number;
  xiaohongshu_fit: number;
  style_consistency: number;
  negative_constraints: number;
  text_risk: number;
  overall_score: number;
}

export interface IterationRound {
  iteration_round: number;
  draft_prompt: string;
  prompt_quality_score: PromptQualityScore;
  failed_items: string[];
  improvement_suggestions: string[];
  whether_need_rewrite: boolean;
  final_image_prompt: string;
}

export interface ImageQualityCheck {
  is_relevant_to_topic: boolean;
  has_text_or_garbled_text: boolean;
  has_logo_or_watermark: boolean;
  has_qrcode: boolean;
  has_sensitive_content: boolean;
  has_deformed_face_or_hands: boolean;
  is_xiaohongshu_cover_ready: boolean;
  has_title_space: boolean;
  need_retry: boolean;
  retry_reason: string;
  vision_check_status?: "checked" | "skipped" | "failed" | string;
  vision_check_message?: string;
}

export interface AgentDraftBatchResult {
  items: AgentDraftItem[];
  created_count: number;
  failed_count: number;
}

export interface XhsAgentRunPayload extends AgentDraftPayload {
  n?: number;
}

export interface XhsAgentResearchNote {
  id: number;
  note_id: string;
  title: string;
  content: string;
  author_name: string;
}

export interface XhsAgentResearchSearchCandidate {
  keyword: string;
  note_id: string;
  title: string;
  content: string;
  author_name: string;
  note_url: string;
  likes: number;
  collects: number;
  comments: number;
}

export interface XhsAgentResearch {
  keywords: string[];
  reference_notes: XhsAgentResearchNote[];
  search?: {
    enabled: boolean;
    account_id?: number;
    keywords?: string[];
    candidate_count?: number;
    saved_count?: number;
    candidates?: XhsAgentResearchSearchCandidate[];
    saved_notes?: XhsAgentResearchNote[];
  };
}

export interface XhsAgentRunResult {
  run_id: number;
  status: string;
  progress?: number;
  account_check?: Record<string, unknown>;
  model_check?: Record<string, unknown>;
  publish_preview?: Record<string, unknown>;
  research?: XhsAgentResearch;
  result?: AgentDraftBatchResult;
  report?: {
    file_name: string;
    file_path: string;
    download_url: string;
  };
  publish_confirmation?: {
    created_count: number;
    publish_job_ids: number[];
    draft_ids: number[];
    publish_mode: "immediate" | "scheduled" | string;
  };
}

export interface ConfirmXhsAgentRunPayload {
  platform_account_id?: number | null;
  draft_ids?: number[];
  publish_mode?: "immediate" | "scheduled";
  scheduled_at?: string | null;
  topics?: string[];
  location?: string | null;
  privacy_type?: 0 | 1 | number | null;
  is_private?: boolean | null;
}

export interface XhsAgentPublishJobPreview {
  id: number;
  platform_account_id?: number | null;
  source_draft_id?: number | null;
  platform: PlatformId;
  title: string;
  body: string;
  publish_mode: "immediate" | "scheduled" | string;
  publish_options: PublishOptions;
  status: string;
  scheduled_at?: string | null;
  created_at: string;
}

export interface ConfirmXhsAgentRunResult {
  run_id: number;
  created_count: number;
  items: XhsAgentPublishJobPreview[];
  message: string;
}

export interface SourceImage {
  id: string;
  role: string;
  url: string;
}

export type ImageEditTaskType =
  | "style_transfer"
  | "room_makeover"
  | "material_replace"
  | "lighting_enhance"
  | "declutter"
  | "cover_composition"
  | "detail_enhance"
  | "variation";

export type ImageEditDomain = "home_decor" | "general";
export type ImageEditOutputGoal = "xhs_cover" | "xhs_body" | "general";
export type ImageEditRealismLevel = "low" | "medium" | "high";
export type ImageEditArtifactStatus = "pending" | "planning" | "generating" | "reviewing" | "completed" | "failed";
export type ImageEditCheckStatus = "pass" | "warning" | "fail" | "skipped";

export interface EditAiImagePayload {
  source_images: SourceImage[];
  task_type: ImageEditTaskType;
  domain?: ImageEditDomain;
  edit_intent: string;
  preserve?: string[];
  change?: string[];
  avoid?: string[];
  output_goal?: ImageEditOutputGoal;
  realism_level?: ImageEditRealismLevel;
  room_type?: string | null;
  decor_style?: string | null;
  model?: string | null;
  n?: number;
  size?: string | null;
  quality?: string | null;
  style?: string | null;
  response_format?: string | null;
  save_to_assets?: boolean;
}

export interface ImageEditSpec {
  source_images: SourceImage[];
  task_type: ImageEditTaskType;
  domain: ImageEditDomain;
  edit_intent: string;
  preserve: string[];
  change: string[];
  avoid: string[];
  output_goal: ImageEditOutputGoal;
  realism_level: ImageEditRealismLevel;
  room_type?: string | null;
  decor_style?: string | null;
}

export interface ImageEditPlanStep {
  step: number;
  name: string;
  instruction: string;
}

export interface ImageEditPlan {
  layout_policy: string;
  style_policy: string;
  material_policy: string;
  lighting_policy: string;
  composition_policy: string;
  steps: ImageEditPlanStep[];
}

export interface ImageEditCompiledPrompts {
  positive_prompt: string;
  negative_prompt: string;
  compiler_version: string;
}

export interface ImageEditResultAsset {
  url: string;
  width?: number | null;
  height?: number | null;
}

export interface ImageEditQualityCheckItem {
  name: string;
  status: ImageEditCheckStatus;
  message: string;
}

export interface ImageEditQualityReport {
  passed: boolean;
  checks: ImageEditQualityCheckItem[];
}

export interface ImageEditProvenance {
  model_config_id?: number | null;
  model_name?: string | null;
  created_at: string;
  knowledge_base?: string | null;
  prompt_compiler: string;
}

export interface ImageEditReport {
  file_name: string;
  file_path: string;
  download_url: string;
}

export interface ImageGenerationArtifact {
  request_id: string;
  status: ImageEditArtifactStatus;
  source_images: SourceImage[];
  normalized_spec?: ImageEditSpec | null;
  edit_plan?: ImageEditPlan | null;
  compiled_prompts?: ImageEditCompiledPrompts | null;
  result_assets: ImageEditResultAsset[];
  quality_report?: ImageEditQualityReport | null;
  provenance: ImageEditProvenance;
  report?: ImageEditReport | null;
  errors: string[];
}
