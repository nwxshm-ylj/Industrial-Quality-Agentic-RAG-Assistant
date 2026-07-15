import { apiClient } from "./client";
import type {
  FeedbackCreateRequest,
  FeedbackItem,
  FeedbackRating,
  FeedbackResponse,
  FeedbackStatsResponse,
} from "./types";

interface FeedbackListParams {
  rating?: FeedbackRating;
  username?: string;
  limit?: number;
}

export const feedbackApi = {
  async submit(payload: FeedbackCreateRequest): Promise<FeedbackResponse> {
    const response = await apiClient.post<FeedbackResponse>("/feedback", payload);
    return response.data;
  },

  async list(params: FeedbackListParams = {}): Promise<FeedbackItem[]> {
    const response = await apiClient.get<FeedbackItem[]>("/feedback", {
      params: {
        ...(params.rating ? { rating: params.rating } : {}),
        ...(params.username ? { username: params.username } : {}),
        limit: params.limit || 100,
      },
    });
    return response.data;
  },

  async stats(): Promise<FeedbackStatsResponse> {
    const response = await apiClient.get<FeedbackStatsResponse>("/feedback/stats");
    return response.data;
  },
};
