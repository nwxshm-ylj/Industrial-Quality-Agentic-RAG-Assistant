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
type GeneratedEvalRunInfo = components["schemas"]["EvalRunInfo"];
type GeneratedEvalItemInfo = components["schemas"]["EvalItemInfo"];

export interface GenerationEvalMetrics extends Record<string, number> {
  overall_pass_rate: number;
  citation_validation_pass_rate: number;
  avg_citation_coverage: number;
  semantic_validation_coverage_rate: number;
  semantic_support_pass_rate: number;
  avg_semantic_support_rate: number;
  repair_trigger_rate: number;
  repair_success_rate: number;
  llm_repair_selection_rate: number;
  deterministic_prune_selection_rate: number;
  direct_finalize_selection_rate: number;
  repair_avoidance_rate: number;
  avg_latency_llm_repair_ms: number;
  avg_latency_without_llm_repair_ms: number;
  deterministic_citation_pruning_rate: number;
  final_refusal_rate: number;
  abstention_accuracy: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
}

export type EvalItemInfo = GeneratedEvalItemInfo & {
  category?: string | null;
  answerable?: boolean | null;
  must_cite?: boolean | null;
  should_abstain?: boolean | null;
  answer_abstained?: boolean | null;
  abstention_ok?: boolean | null;
  citation_contract_ok?: boolean | null;
  citation_coverage?: number | null;
  semantic_support_checked?: boolean;
  semantic_support_rate?: number | null;
  semantic_support_ok?: boolean | null;
  semantic_validation_degraded?: boolean;
  validation_action?: string | null;
  generation_retry_count?: number;
  repair_triggered?: boolean;
  repair_avoided?: boolean;
  repair_success?: boolean;
  citation_pruned?: boolean;
    failure_category?: string | null;
    failure_tags?: string[];
    evidence_enough?: boolean | null;
    evidence_confidence?: number | null;
    evidence_threshold?: number | null;
    evidence_reasons?: string[];
    missing_aspects?: string[];
    abstain_reason?: string | null;
    answer_validation_history?: Array<Record<string, unknown>>;
  quality_checks?: Record<string, boolean>;
};

  export type EvalRunInfo = GeneratedEvalRunInfo & {
    generation_metrics?: Partial<GenerationEvalMetrics>;
    failure_analysis?: {
      failed_count?: number;
      passed_count?: number;
      false_refusal_count?: number;
      false_refusal_rate?: number;
      knowledge_gap_refusal_accuracy?: number;
      failure_categories?: Record<string, number>;
      failure_tags?: Record<string, number>;
      evidence_threshold_sweep?: Array<{
        threshold: number;
        sample_count: number;
        decision_accuracy: number;
        false_refusal_rate: number;
        unsafe_answer_rate: number;
      }>;
    };
  prompt_release?: Record<string, unknown> | null;
  evaluation_fingerprint?: Record<string, unknown> | null;
};

export type EvalRunResponse = EvalRunInfo & { items: EvalItemInfo[] };
export interface EvalRunListResponse {
  runs: EvalRunInfo[];
  total: number;
}

export interface GenerationEvalRunRequest {
  max_questions?: number | null;
  question_ids?: string[] | null;
}
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

export type ChatProgressStatus = "running" | "completed" | "error";

export interface ChatAcceptedEvent {
  sequence: number;
  request_id: string;
  session_id: string;
  status: "accepted";
}

export interface ChatProgressEvent {
  sequence: number;
  request_id: string;
  session_id: string;
  node_name: string;
  label: string;
  status: ChatProgressStatus;
  progress: number;
  intent?: string | null;
  retry_count?: number;
  latency_ms?: number;
  error_message?: string;
}

export interface ChatTokenEvent {
  sequence: number;
  request_id: string;
  session_id: string;
  delta: string;
}

export interface ChatAnswerReplaceEvent {
  sequence: number;
  request_id: string;
  session_id: string;
  answer: string;
}

export interface ChatStreamErrorEvent {
  sequence: number;
  request_id: string;
  session_id: string;
  status_code: number;
  error_code: string;
  message: string;
  retryable: boolean;
}

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
  generation_retry_count?: number | null;
  generation_repair_error?: string | null;
  generation_quality_passed?: boolean | null;
  answer_validation?: Record<string, unknown> | null;
  answer_structure?: Record<string, unknown> | null;
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
