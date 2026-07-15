import type { components } from "./generated/schema";

export type Role = components["schemas"]["UserInfo"]["role"];
export type UserInfo = components["schemas"]["UserInfo"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type LoginResponse = components["schemas"]["LoginResponse"];
export type CreateUserRequest = components["schemas"]["CreateUserRequest"];
export type CreateUserResponse = components["schemas"]["CreateUserResponse"];
export type ChatRequest = components["schemas"]["ChatRequest"];
export type Citation = components["schemas"]["Citation"];
export type DocumentInfo = components["schemas"]["DocumentInfo"];
export type DocumentListResponse = components["schemas"]["DocumentListResponse"];
export type DocumentUploadResponse = components["schemas"]["DocumentUploadResponse"];
export type DocumentDeleteResponse = components["schemas"]["DocumentDeleteResponse"];
export type DocumentReindexResponse = components["schemas"]["DocumentReindexResponse"];
export type FeedbackCreateRequest = components["schemas"]["FeedbackCreateRequest"];
export type FeedbackResponse = components["schemas"]["FeedbackResponse"];
export type FeedbackItem = components["schemas"]["FeedbackItem"];
export type FeedbackStatsResponse = components["schemas"]["FeedbackStatsResponse"];
export type FeedbackRating = FeedbackCreateRequest["rating"];
export type EvalRunInfo = components["schemas"]["EvalRunInfo"];
export type EvalRunResponse = components["schemas"]["EvalRunResponse"];
export type EvalRunListResponse = components["schemas"]["EvalRunListResponse"];
export type EvalItemInfo = components["schemas"]["EvalItemInfo"];
export type UsageOverviewResponse = components["schemas"]["UsageOverviewResponse"];
export type UsageTimeseriesItem = components["schemas"]["UsageTimeseriesItem"];
export type UsageTimeseriesResponse = components["schemas"]["UsageTimeseriesResponse"];
export type ModelUsageItem = components["schemas"]["ModelUsageItem"];
export type ModelUsageResponse = components["schemas"]["ModelUsageResponse"];
export type IntentUsageItem = components["schemas"]["IntentUsageItem"];
export type IntentUsageResponse = components["schemas"]["IntentUsageResponse"];
export type RetrievalUsageItem = components["schemas"]["RetrievalUsageItem"];
export type RetrievalUsageResponse = components["schemas"]["RetrievalUsageResponse"];
export type RequestUsageDetailsResponse = components["schemas"]["RequestUsageDetailsResponse"];

export interface RetrievalEvalRunRequest {
  top_k: number;
  k_values: number[];
  max_questions?: number | null;
}

export interface RetrievalEvalRunSummary {
  total_questions: number;
  successful_questions: number;
  failed_questions: number;
  degraded_questions: number;
  degraded_rate: number;
}

export interface RetrievalEvalRunInfo {
  run_id: string;
  status: string;
  dataset_name?: string | null;
  started_at: string;
  completed_at: string;
  username?: string | null;
  config: Record<string, unknown>;
  summary: RetrievalEvalRunSummary;
  metrics: Record<string, number>;
  latency: Record<string, unknown>;
  report_path?: string | null;
}

export interface RetrievalEvalRunResponse extends RetrievalEvalRunInfo {
  items: Array<Record<string, unknown>>;
}

export interface RetrievalEvalRunListResponse {
  runs: RetrievalEvalRunInfo[];
  total: number;
}

export interface MemoryMessage {
  role?: string;
  content?: string;
  intent?: string | null;
  created_at?: string;
  [key: string]: unknown;
}

export interface ChatUsage extends Record<string, unknown> {
  llm_call_count?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  embedding_tokens?: number | null;
  calculated_cost?: number | null;
}

export interface ChatMetadata extends Record<string, unknown> {
  intent?: string | null;
  evidence_score?: number | null;
  evidence_enough?: boolean | null;
  retry_count?: number | null;
  total_latency_ms?: number | null;
  retrieval_mode?: string | null;
  degraded?: boolean | null;
  degraded_reason?: string | null;
  trace_id?: string | null;
  prompt_release?: string | null;
  prompt_versions?: Record<string, string> | null;
  usage?: ChatUsage | null;
}

type GeneratedChatResponse = components["schemas"]["ChatResponse"];

export type ChatResponse = Omit<
  GeneratedChatResponse,
  "metadata" | "memory_messages"
> & {
  metadata?: ChatMetadata | null;
  memory_messages?: MemoryMessage[] | null;
};

export interface HealthResponse {
  status: string;
}

export interface ReadinessCheck {
  status: string;
  error_type?: string;
  release_id?: string;
  channel?: string;
}

export interface ReadinessResponse {
  status: "ready" | "degraded" | "not_ready" | string;
  checks: Record<string, ReadinessCheck>;
}

export interface AuditLogItem {
  id: number;
  request_id?: string | null;
  session_id?: string | null;
  username?: string | null;
  role?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  status?: string | null;
  detail?: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditActionCount {
  action: string;
  count: number;
}

export interface AuditLogStatsResponse {
  total: number;
  success_count: number;
  denied_count: number;
  failed_count: number;
  top_actions: AuditActionCount[];
}

export interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string }>;
}
