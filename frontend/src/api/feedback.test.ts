import { vi } from "vitest";

import { apiClient } from "./client";
import { feedbackApi } from "./feedback";

describe("feedbackApi", () => {
  afterEach(() => vi.restoreAllMocks());

  it("submits the graph response compatibility fields", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      data: { id: 1, status: "success", message: "反馈已记录" },
    });
    const payload = {
      request_id: "req-1",
      session_id: "session-1",
      question: "q",
      answer: "a",
      rating: "positive" as const,
      intent: "doc_qa",
      citations: [],
      metadata: { total_latency_ms: 80 },
    };

    await feedbackApi.submit(payload);
    expect(post).toHaveBeenCalledWith("/feedback", payload);
  });

  it("keeps feedback list filters within the API contract", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: [] });
    await feedbackApi.list({ rating: "negative", limit: 20 });
    expect(get).toHaveBeenCalledWith("/feedback", {
      params: { rating: "negative", limit: 20 },
    });
  });
});
