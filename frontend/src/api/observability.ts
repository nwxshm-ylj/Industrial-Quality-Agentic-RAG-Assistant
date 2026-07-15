import { apiClient } from "./client";
import type {
  IntentUsageResponse,
  ModelUsageResponse,
  RequestUsageDetailsResponse,
  RetrievalUsageResponse,
  UsageOverviewResponse,
  UsageTimeseriesResponse,
} from "./types";

export interface AnalyticsRange {
  startAt: string;
  endAt: string;
}

function rangeParams(range: AnalyticsRange) {
  return { start_at: range.startAt, end_at: range.endAt };
}

export const observabilityApi = {
  async overview(range: AnalyticsRange): Promise<UsageOverviewResponse> {
    const response = await apiClient.get<UsageOverviewResponse>(
      "/observability/analytics/overview",
      { params: rangeParams(range) },
    );
    return response.data;
  },

  async timeseries(range: AnalyticsRange, granularity: "hour" | "day"): Promise<UsageTimeseriesResponse> {
    const response = await apiClient.get<UsageTimeseriesResponse>(
      "/observability/analytics/timeseries",
      { params: { ...rangeParams(range), granularity } },
    );
    return response.data;
  },

  async models(range: AnalyticsRange): Promise<ModelUsageResponse> {
    const response = await apiClient.get<ModelUsageResponse>(
      "/observability/analytics/models",
      { params: rangeParams(range) },
    );
    return response.data;
  },

  async intents(range: AnalyticsRange): Promise<IntentUsageResponse> {
    const response = await apiClient.get<IntentUsageResponse>(
      "/observability/analytics/intents",
      { params: rangeParams(range) },
    );
    return response.data;
  },

  async retrieval(range: AnalyticsRange): Promise<RetrievalUsageResponse> {
    const response = await apiClient.get<RetrievalUsageResponse>(
      "/observability/analytics/retrieval",
      { params: rangeParams(range) },
    );
    return response.data;
  },

  async requestDetails(requestId: string): Promise<RequestUsageDetailsResponse> {
    const response = await apiClient.get<RequestUsageDetailsResponse>(
      `/observability/requests/${encodeURIComponent(requestId)}`,
    );
    return response.data;
  },
};
