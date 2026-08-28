import { vi } from "vitest";

import { chatApi, consumeSseStream } from "./chat";
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
      retrieval_mode: "case_trace",
      multimodal_query: {
        images: ["data:image/png;base64,AAAA"],
      },
    })).resolves.toEqual(response);

    expect(post).toHaveBeenCalledWith(
      "/graph-chat",
      {
        question: "轮毂识别异常可能是什么原因？",
        top_k: 5,
        session_id: "session-1",
        retrieval_mode: "case_trace",
        multimodal_query: {
          images: ["data:image/png;base64,AAAA"],
        },
      },
      { timeout: 180_000 },
    );
  });

  it("parses fragmented SSE progress, token and result events", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      "event: accepted\ndata: {\"request_id\":\"request-1\",",
      "\"session_id\":\"session-1\",\"sequence\":0,\"status\":\"accepted\"}\n\n",
      "event: progress\ndata: {\"node_name\":\"retrieve\",\"label\":\"执行混合检索\",\"status\":\"running\",\"progress\":38}\n\n",
      "event: token\ndata: {\"delta\":\"优先检查\"}\n\n",
      "event: answer_replace\ndata: {\"answer\":\"优先检查【资料1】。\"}\n\n",
    ];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    });
    const events: Array<{ event: string; data: Record<string, unknown> }> = [];

    await consumeSseStream(stream, (event) => events.push(event));

    expect(events).toHaveLength(4);
    expect(events[0]).toMatchObject({ event: "accepted", data: { request_id: "request-1" } });
    expect(events[1]).toMatchObject({ event: "progress", data: { node_name: "retrieve", progress: 38 } });
    expect(events[2]).toMatchObject({ event: "token", data: { delta: "优先检查" } });
    expect(events[3]).toMatchObject({
      event: "answer_replace",
      data: { answer: "优先检查【资料1】。" },
    });
  });
});
