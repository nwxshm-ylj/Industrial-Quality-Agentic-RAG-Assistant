import { vi } from "vitest";

import { chatApi } from "./chat";
import { apiClient } from "./client";

describe("chatApi", () => {
  it("sends the graph-chat compatibility payload", async () => {
    const response = {
      question: "轮毂识别异常可能是什么原因？",
      answer: "请优先检查相机与工位信号。",
      citations: [],
      request_id: "request-1",
      session_id: "session-1",
      metadata: { total_latency_ms: 120 },
    };
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: response });

    await expect(chatApi.ask({
      question: "轮毂识别异常可能是什么原因？",
      top_k: 5,
      session_id: "session-1",
    })).resolves.toEqual(response);

    expect(post).toHaveBeenCalledWith(
      "/graph-chat",
      {
        question: "轮毂识别异常可能是什么原因？",
        top_k: 5,
        session_id: "session-1",
      },
      { timeout: 180_000 },
    );
  });
});
