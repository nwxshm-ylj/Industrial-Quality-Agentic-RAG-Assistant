import type { ChatResponse, Citation } from "../../api/types";

export const intentLabels: Record<string, string> = {
  doc_qa: "文档问答",
  fault_diagnosis: "故障诊断",
  case_search: "历史案例",
  rule_query: "规则查询",
  sql_analysis: "数据分析",
  general: "通用问答",
};

export function formatLatency(value: unknown): string {
  const latency = Number(value);
  if (!Number.isFinite(latency)) {
    return "--";
  }
  return latency >= 1000 ? `${(latency / 1000).toFixed(2)} s` : `${latency.toFixed(0)} ms`;
}

export function formatScore(value: unknown): string {
  const score = Number(value);
  return Number.isFinite(score) ? score.toFixed(3) : "--";
}

export function getIntent(response: ChatResponse): string {
  return response.intent || response.metadata?.intent || "unknown";
}

export function getCitationScore(citation: Citation): number | null {
  const candidates = [
    citation.rerank_score,
    citation.rrf_score,
    citation.hybrid_score,
    citation.score,
    citation.vector_score,
    citation.keyword_score,
    citation.bm25_score,
  ];
  const value = candidates.find((candidate) => typeof candidate === "number");
  return value ?? null;
}

export function shortenId(value: string | null | undefined, size = 8): string {
  if (!value) {
    return "--";
  }
  return value.length > size * 2 + 1
    ? `${value.slice(0, size)}…${value.slice(-size)}`
    : value;
}
