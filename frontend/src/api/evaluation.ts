import { apiClient } from "./client";
import type {
  EvalRunListResponse,
  EvalRunResponse,
  RetrievalEvalRunListResponse,
  RetrievalEvalRunRequest,
  RetrievalEvalRunResponse,
} from "./types";

const EVALUATION_TIMEOUT_MS = 900_000;

export const evaluationApi = {
  async listRuns(limit = 50): Promise<EvalRunListResponse> {
    const response = await apiClient.get<EvalRunListResponse>("/evaluation/runs", {
      params: { limit },
    });
    return response.data;
  },

  async getRun(runId: string): Promise<EvalRunResponse> {
    const response = await apiClient.get<EvalRunResponse>(
      `/evaluation/runs/${encodeURIComponent(runId)}`,
    );
    return response.data;
  },

  async run(): Promise<EvalRunResponse> {
    const response = await apiClient.post<EvalRunResponse>(
      "/evaluation/run",
      undefined,
      { timeout: EVALUATION_TIMEOUT_MS },
    );
    return response.data;
  },

  async listRetrievalRuns(limit = 50): Promise<RetrievalEvalRunListResponse> {
    const response = await apiClient.get<RetrievalEvalRunListResponse>(
      "/evaluation/retrieval/runs",
      { params: { limit } },
    );
    return response.data;
  },

  async getRetrievalRun(runId: string): Promise<RetrievalEvalRunResponse> {
    const response = await apiClient.get<RetrievalEvalRunResponse>(
      `/evaluation/retrieval/runs/${encodeURIComponent(runId)}`,
    );
    return response.data;
  },

  async runRetrieval(payload: RetrievalEvalRunRequest): Promise<RetrievalEvalRunResponse> {
    const response = await apiClient.post<RetrievalEvalRunResponse>(
      "/evaluation/retrieval/run",
      payload,
      { timeout: EVALUATION_TIMEOUT_MS },
    );
    return response.data;
  },
};
