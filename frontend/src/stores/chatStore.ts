import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type {
  ChatAcceptedEvent,
  ChatProgressEvent,
  ChatResponse,
  FeedbackRating,
} from "../api/types";

const MAX_PERSISTED_TURNS = 30;

export type ChatTurnStatus = "pending" | "streaming" | "completed" | "error";

export interface ChatTurn {
  id: string;
  question: string;
  createdAt: string;
  status: ChatTurnStatus;
  requestId?: string;
  streamedAnswer?: string;
  progress?: number;
  currentStage?: ChatProgressEvent;
  progressEvents?: ChatProgressEvent[];
  response?: ChatResponse;
  errorMessage?: string;
}

interface ChatState {
  ownerUsername: string | null;
  sessionId: string;
  topK: number;
  turns: ChatTurn[];
  feedbackRatings: Record<string, FeedbackRating>;
  ensureOwner: (username: string) => void;
  setTopK: (topK: number) => void;
  addPendingTurn: (question: string) => string;
  acceptStreamingTurn: (turnId: string, event: ChatAcceptedEvent) => void;
  updateTurnProgress: (turnId: string, event: ChatProgressEvent) => void;
  appendTurnToken: (turnId: string, delta: string) => void;
  completeTurn: (turnId: string, response: ChatResponse) => void;
  failTurn: (turnId: string, errorMessage: string) => void;
  markFeedback: (requestKey: string, rating: FeedbackRating) => void;
  startNewConversation: () => void;
  clearConversation: () => void;
}

function createId(prefix: string): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  return uuid ? `${prefix}-${uuid}` : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createSessionId(): string {
  return createId("web");
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      ownerUsername: null,
      sessionId: createSessionId(),
      topK: 5,
      turns: [],
      feedbackRatings: {},
      ensureOwner: (username) => {
        set((state) => {
          if (!state.ownerUsername || state.ownerUsername === username) {
            return { ownerUsername: username };
          }
          return {
            ownerUsername: username,
            sessionId: createSessionId(),
            turns: [],
            feedbackRatings: {},
          };
        });
      },
      setTopK: (topK) => set({ topK: Math.min(10, Math.max(1, topK)) }),
      addPendingTurn: (question) => {
        const turnId = createId("turn");
        const turn: ChatTurn = {
          id: turnId,
          question,
          createdAt: new Date().toISOString(),
          status: "pending",
          streamedAnswer: "",
          progress: 0,
          progressEvents: [],
        };
        set((state) => ({
          turns: [...state.turns, turn].slice(-MAX_PERSISTED_TURNS),
        }));
        return turnId;
      },
      acceptStreamingTurn: (turnId, event) => {
        set((state) => ({
          sessionId: event.session_id || state.sessionId,
          turns: state.turns.map((turn) => (
            turn.id === turnId
              ? {
                  ...turn,
                  status: "streaming",
                  requestId: event.request_id,
                  progress: Math.max(turn.progress || 0, 1),
                }
              : turn
          )),
        }));
      },
      updateTurnProgress: (turnId, event) => {
        set((state) => ({
          turns: state.turns.map((turn) => (
            turn.id === turnId
              ? {
                  ...turn,
                  status: event.status === "error" ? "error" : "streaming",
                  requestId: event.request_id || turn.requestId,
                  progress: Math.max(turn.progress || 0, event.progress),
                  currentStage: event,
                  progressEvents: [...(turn.progressEvents || []), event].slice(-30),
                  errorMessage: event.status === "error"
                    ? event.error_message || "工作流节点执行失败"
                    : turn.errorMessage,
                }
              : turn
          )),
        }));
      },
      appendTurnToken: (turnId, delta) => {
        set((state) => ({
          turns: state.turns.map((turn) => (
            turn.id === turnId
              ? {
                  ...turn,
                  status: "streaming",
                  streamedAnswer: `${turn.streamedAnswer || ""}${delta}`,
                }
              : turn
          )),
        }));
      },
      completeTurn: (turnId, response) => {
        set((state) => ({
          sessionId: response.session_id || state.sessionId,
          turns: state.turns.map((turn) => (
            turn.id === turnId
              ? {
                  ...turn,
                  status: "completed",
                  requestId: response.request_id || turn.requestId,
                  streamedAnswer: response.answer,
                  progress: 100,
                  response,
                  errorMessage: undefined,
                }
              : turn
          )),
        }));
      },
      failTurn: (turnId, errorMessage) => {
        set((state) => ({
          turns: state.turns.map((turn) => (
            turn.id === turnId
              ? { ...turn, status: "error", errorMessage }
              : turn
          )),
        }));
      },
      markFeedback: (requestKey, rating) => {
        set((state) => ({
          feedbackRatings: { ...state.feedbackRatings, [requestKey]: rating },
        }));
      },
      startNewConversation: () => set({
        sessionId: createSessionId(),
        turns: [],
        feedbackRatings: {},
      }),
      clearConversation: () => set({
        ownerUsername: null,
        sessionId: createSessionId(),
        topK: 5,
        turns: [],
        feedbackRatings: {},
      }),
    }),
    {
      name: "industrial-rag-chat-v1",
      storage: createJSONStorage(() => sessionStorage),
      partialize: ({ ownerUsername, sessionId, topK, turns, feedbackRatings }) => ({
        ownerUsername,
        sessionId,
        topK,
        turns,
        feedbackRatings,
      }),
    },
  ),
);

export function getLatestCompletedResponse(turns: ChatTurn[]): ChatResponse | null {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const turn = turns[index];
    if (turn.status === "completed" && turn.response) {
      return turn.response;
    }
  }
  return null;
}
