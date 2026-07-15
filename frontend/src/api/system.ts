import axios from "axios";

import type { HealthResponse, ReadinessResponse } from "./types";

const healthClient = axios.create({
  timeout: 5_000,
});

export const systemApi = {
  async liveness(): Promise<HealthResponse> {
    const response = await healthClient.get<HealthResponse>("/health/live");
    return response.data;
  },

  async readiness(): Promise<ReadinessResponse> {
    const response = await healthClient.get<ReadinessResponse>("/health/ready", {
      validateStatus: (status) => status === 200 || status === 503,
    });
    return response.data;
  },
};
