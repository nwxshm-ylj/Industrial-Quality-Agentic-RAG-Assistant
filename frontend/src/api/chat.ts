import { apiClient } from "./client";
import type { ChatRequest, ChatResponse } from "./types";

const GRAPH_CHAT_TIMEOUT_MS = 180_000;

export const chatApi = {
  async ask(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>("/graph-chat", request, {
      timeout: GRAPH_CHAT_TIMEOUT_MS,
    });
    return response.data;
  },
};
