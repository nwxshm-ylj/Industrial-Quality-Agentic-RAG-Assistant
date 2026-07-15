import { vi } from "vitest";

import { apiClient } from "./client";
import { evaluationApi } from "./evaluation";

describe("evaluationApi", () => {
  afterEach(() => vi.restoreAllMocks());

  it("uses the long-running timeout for generation evaluation", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    await evaluationApi.run();
    expect(post).toHaveBeenCalledWith(
      "/evaluation/run",
      undefined,
      { timeout: 900_000 },
    );
  });

  it("sends retrieval-only evaluation configuration", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    const payload = { top_k: 10, k_values: [1, 3, 5, 10], max_questions: 20 };
    await evaluationApi.runRetrieval(payload);
    expect(post).toHaveBeenCalledWith(
      "/evaluation/retrieval/run",
      payload,
      { timeout: 900_000 },
    );
  });
});
