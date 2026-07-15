import {
  formatRate,
  getRetrievalK,
  getRetrievalLatency,
  getRetrievalMetric,
} from "./presentation";

const run = {
  run_id: "retrieval-1",
  status: "completed",
  started_at: "2026-07-14T00:00:00Z",
  completed_at: "2026-07-14T00:01:00Z",
  config: { k_values: [1, 3, 5] },
  summary: {
    total_questions: 10,
    successful_questions: 10,
    failed_questions: 0,
    degraded_questions: 1,
    degraded_rate: 0.1,
  },
  metrics: { "recall@5": 0.9, "mrr@5": 0.8 },
  latency: { retrieval_total: { p95_ms: 120 } },
};

describe("evaluation presentation", () => {
  it("formats rates and discovers the configured max K", () => {
    expect(formatRate(0.856)).toBe("85.6%");
    expect(getRetrievalK(run)).toBe(5);
  });

  it("reads metric and latency dictionaries without SDK types", () => {
    expect(getRetrievalMetric(run, "recall")).toBe(0.9);
    expect(getRetrievalLatency(run, "p95")).toBe(120);
  });
});
