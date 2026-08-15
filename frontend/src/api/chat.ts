import { useAuthStore } from "../stores/authStore";
import { apiBaseUrl, apiClient } from "./client";
import type {
  ChatAcceptedEvent,
  ChatAnswerReplaceEvent,
  ChatProgressEvent,
  ChatRequest,
  ChatResponse,
  ChatStreamErrorEvent,
  ChatTokenEvent,
} from "./types";

const GRAPH_CHAT_TIMEOUT_MS = 180_000;

export interface ChatStreamHandlers {
  onAccepted?: (event: ChatAcceptedEvent) => void;
  onProgress?: (event: ChatProgressEvent) => void;
  onToken?: (event: ChatTokenEvent) => void;
  onAnswerReplace?: (event: ChatAnswerReplaceEvent) => void;
  onResult?: (response: ChatResponse) => void;
  onDone?: (event: { request_id: string; session_id: string }) => void;
}

interface ParsedSseEvent {
  event: string;
  data: Record<string, unknown>;
}

export class ChatStreamError extends Error {
  readonly code: string;
  readonly requestId?: string;
  readonly retryable: boolean;

  constructor(message: string, options?: { code?: string; requestId?: string; retryable?: boolean }) {
    super(message);
    this.name = "ChatStreamError";
    this.code = options?.code || "STREAM_ERROR";
    this.requestId = options?.requestId;
    this.retryable = options?.retryable ?? false;
  }
}

export const chatApi = {
  async ask(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>("/graph-chat", request, {
      timeout: GRAPH_CHAT_TIMEOUT_MS,
    });
    return response.data;
  },

  async askStream(
    request: ChatRequest,
    handlers: ChatStreamHandlers,
    signal?: AbortSignal,
  ): Promise<ChatResponse> {
    const token = useAuthStore.getState().accessToken;
    const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/graph-chat/stream`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
      signal,
    });

    if (response.status === 401) {
      useAuthStore.getState().logout();
    }
    if (!response.ok) {
      throw new ChatStreamError(await readHttpError(response), {
        code: `HTTP_${response.status}`,
        retryable: response.status >= 500,
      });
    }
    if (!response.body) {
      throw new ChatStreamError("浏览器未收到流式响应体", {
        code: "EMPTY_STREAM",
        retryable: true,
      });
    }

    let finalResponse: ChatResponse | null = null;
    let streamError: ChatStreamError | null = null;

    await consumeSseStream(response.body, ({ event, data }) => {
      if (event === "accepted") {
        handlers.onAccepted?.(data as unknown as ChatAcceptedEvent);
      } else if (event === "progress") {
        handlers.onProgress?.(data as unknown as ChatProgressEvent);
      } else if (event === "token") {
        handlers.onToken?.(data as unknown as ChatTokenEvent);
      } else if (event === "answer_replace") {
        handlers.onAnswerReplace?.(data as unknown as ChatAnswerReplaceEvent);
      } else if (event === "result") {
        finalResponse = data.response as ChatResponse;
        handlers.onResult?.(finalResponse);
      } else if (event === "error") {
        const errorEvent = data as unknown as ChatStreamErrorEvent;
        streamError = new ChatStreamError(errorEvent.message, {
          code: errorEvent.error_code,
          requestId: errorEvent.request_id,
          retryable: errorEvent.retryable,
        });
      } else if (event === "done") {
        handlers.onDone?.({
          request_id: String(data.request_id || ""),
          session_id: String(data.session_id || ""),
        });
      }
    });

    if (streamError) {
      throw streamError;
    }
    if (!finalResponse) {
      throw new ChatStreamError("流式响应结束，但未收到最终结果", {
        code: "RESULT_MISSING",
        retryable: true,
      });
    }
    return finalResponse;
  },
};


export async function consumeSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: ParsedSseEvent) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");

      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseSseFrame(frame);
        if (parsed) {
          onEvent(parsed);
        }
        boundary = buffer.indexOf("\n\n");
      }
    }

    const parsed = parseSseFrame(buffer.trim());
    if (parsed) {
      onEvent(parsed);
    }
  } finally {
    reader.releaseLock();
  }
}


function parseSseFrame(frame: string): ParsedSseEvent | null {
  if (!frame || frame.startsWith(":")) {
    return null;
  }
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (!dataLines.length) {
    return null;
  }
  const parsed = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
  return { event, data: parsed };
}


async function readHttpError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    return typeof payload.detail === "string"
      ? payload.detail
      : `请求失败（HTTP ${response.status}）`;
  } catch {
    return `请求失败（HTTP ${response.status}）`;
  }
}
