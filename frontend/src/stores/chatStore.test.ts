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
    const turnId = useChatStore.getState().addPendingTurn("第一问");
    expect(useChatStore.getState().turns[0].status).toBe("pending");

    useChatStore.getState().completeTurn(turnId, response);

    expect(useChatStore.getState().sessionId).toBe("session-from-api");
    expect(useChatStore.getState().turns[0].status).toBe("completed");
    expect(getLatestCompletedResponse(useChatStore.getState().turns)).toEqual(response);
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

  it("remembers submitted feedback per request", () => {
    useChatStore.getState().markFeedback("request-1", "positive");
    expect(useChatStore.getState().feedbackRatings["request-1"]).toBe("positive");
  });
});
