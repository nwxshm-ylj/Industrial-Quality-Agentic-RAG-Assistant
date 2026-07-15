import type { RetrievalEvalRunInfo } from "../../api/types";

export function formatRate(value: number | null | undefined): string {
  return `${((value || 0) * 100).toFixed(1)}%`;
}

export function formatMetric(value: number | null | undefined, digits = 3): string {
  return Number(value || 0).toFixed(digits);
}

export function getRetrievalK(run: RetrievalEvalRunInfo): number {
  const values = run.config.k_values;
  if (!Array.isArray(values)) {
    return 5;
  }
  const numeric = values.map(Number).filter(Number.isFinite);
  return numeric.length ? Math.max(...numeric) : 5;
}

export function getRetrievalMetric(run: RetrievalEvalRunInfo, name: string): number {
  const k = getRetrievalK(run);
  return Number(run.metrics[`${name}@${k}`] || 0);
}

export function getRetrievalLatency(run: RetrievalEvalRunInfo, percentile: string): number {
  const total = run.latency.retrieval_total;
  if (!total || typeof total !== "object") {
    return 0;
  }
  return Number((total as Record<string, unknown>)[`${percentile}_ms`] || 0);
}
