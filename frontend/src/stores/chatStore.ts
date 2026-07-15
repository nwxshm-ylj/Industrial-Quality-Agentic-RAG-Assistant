import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { ChatResponse, FeedbackRating } from "../api/types";

const MAX_PERSISTED_TURNS = 30;

export type ChatTurnStatus = "pending" | "completed" | "error";

export interface ChatTurn {
  id: string;
  question: string;
  createdAt: string;
  status: ChatTurnStatus;
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
        };
        set((state) => ({
          turns: [...state.turns, turn].slice(-MAX_PERSISTED_TURNS),
        }));
        return turnId;
      },
      completeTurn: (turnId, response) => {
        set((state) => ({
          sessionId: response.session_id || state.sessionId,
          turns: state.turns.map((turn) => (
            turn.id === turnId
              ? { ...turn, status: "completed", response, errorMessage: undefined }
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
