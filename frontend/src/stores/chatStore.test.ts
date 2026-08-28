import { useChatStore, getLatestCompletedResponse } from "./chatStore";

const response = {
  question: "第一问",
  answer: "第一答",
  citations: [],
  request_id: "request-1",
  session_id: "session-from-api",
  metadata: { total_latency_ms: 88 },
};

describe("chatStore", () => {
  beforeEach(() => {
    sessionStorage.clear();
    useChatStore.getState().clearConversation();
    useChatStore.getState().ensureOwner("engineer-a");
  });

  it("tracks a pending turn and completes it with the backend session", () => {
    useChatStore.getState().setRetrievalMode("case_trace");
    const turnId = useChatStore.getState().addPendingTurn("第一问", [
      {
        id: "image-1",
        name: "defect.png",
        dataUrl: "data:image/png;base64,AAAA",
      },
    ]);
    expect(useChatStore.getState().turns[0].status).toBe("pending");
    expect(useChatStore.getState().turns[0].images?.[0].name).toBe("defect.png");
    expect(useChatStore.getState().turns[0].retrievalMode).toBe("case_trace");

    useChatStore.getState().completeTurn(turnId, response);

    expect(useChatStore.getState().sessionId).toBe("session-from-api");
    expect(useChatStore.getState().turns[0].status).toBe("completed");
    expect(getLatestCompletedResponse(useChatStore.getState().turns)).toEqual(response);
  });

  it("tracks accepted, node progress and streamed answer tokens", () => {
    const turnId = useChatStore.getState().addPendingTurn("流式问题");
    useChatStore.getState().acceptStreamingTurn(turnId, {
      sequence: 0,
      request_id: "request-stream",
      session_id: "session-stream",
      status: "accepted",
    });
    useChatStore.getState().updateTurnProgress(turnId, {
      sequence: 1,
      request_id: "request-stream",
      session_id: "session-stream",
      node_name: "retrieve",
      label: "执行混合检索",
      status: "running",
      progress: 38,
    });
    useChatStore.getState().updateTurnProgress(turnId, {
      sequence: 2,
      request_id: "request-stream",
      session_id: "session-stream",
      node_name: "retrieve",
      label: "执行混合检索",
      status: "completed",
      progress: 55,
      latency_ms: 42,
    });
    useChatStore.getState().appendTurnToken(turnId, "优先");
    useChatStore.getState().appendTurnToken(turnId, "检查相机");
    useChatStore.getState().replaceTurnAnswer(turnId, "优先检查相机【资料1】。");

    expect(useChatStore.getState().turns[0]).toMatchObject({
      status: "streaming",
      requestId: "request-stream",
      progress: 55,
      streamedAnswer: "优先检查相机【资料1】。",
      currentStage: { node_name: "retrieve" },
    });

    useChatStore.getState().completeTurn(turnId, {
      ...response,
      question: "流式问题",
      answer: "优先检查相机【资料1】。",
    });
    expect(useChatStore.getState().turns[0].progressEvents).toHaveLength(2);
    expect(useChatStore.getState().turns[0].progressEvents?.[1]).toMatchObject({
      node_name: "retrieve",
      status: "completed",
      latency_ms: 42,
    });
  });

  it("isolates conversations when the authenticated user changes", () => {
    const previousSession = useChatStore.getState().sessionId;
    useChatStore.getState().addPendingTurn("不应跨用户保留");

    useChatStore.getState().ensureOwner("viewer-b");

    expect(useChatStore.getState().ownerUsername).toBe("viewer-b");
    expect(useChatStore.getState().sessionId).not.toBe(previousSession);
    expect(useChatStore.getState().turns).toHaveLength(0);
  });

  it("records request failures without losing the user question", () => {
    const turnId = useChatStore.getState().addPendingTurn("失败问题");
    useChatStore.getState().failTurn(turnId, "API unavailable");

    expect(useChatStore.getState().turns[0]).toMatchObject({
      question: "失败问题",
      status: "error",
      errorMessage: "API unavailable",
    });
  });

  it("clamps top_k to the backend contract", () => {
    useChatStore.getState().setTopK(99);
    expect(useChatStore.getState().topK).toBe(10);
    useChatStore.getState().setTopK(0);
    expect(useChatStore.getState().topK).toBe(1);
  });

  it("keeps the selected mode in the current conversation and resets a new one", () => {
    useChatStore.getState().setRetrievalMode("case_trace");
    useChatStore.getState().addPendingTurn("追溯问题");

    expect(useChatStore.getState().retrievalMode).toBe("case_trace");
    expect(useChatStore.getState().turns[0].retrievalMode).toBe("case_trace");

    useChatStore.getState().startNewConversation();
    expect(useChatStore.getState().retrievalMode).toBe("knowledge");
  });

  it("remembers submitted feedback per request", () => {
    useChatStore.getState().markFeedback("request-1", "positive");
    expect(useChatStore.getState().feedbackRatings["request-1"]).toBe("positive");
  });
});
