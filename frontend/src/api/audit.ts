import { apiClient } from "./client";
import type { AuditLogListResponse, AuditLogStatsResponse } from "./types";

export interface AuditLogQuery {
  username?: string;
  action?: string;
  status?: string;
  request_id?: string;
  start_at?: string;
  end_at?: string;
  limit?: number;
  offset?: number;
}

export interface AuditStatsQuery {
  start_at?: string;
  end_at?: string;
}

export const auditApi = {
  async list(params: AuditLogQuery = {}): Promise<AuditLogListResponse> {
    const response = await apiClient.get<AuditLogListResponse>("/audit-logs", { params });
    return response.data;
  },

  async stats(params: AuditStatsQuery = {}): Promise<AuditLogStatsResponse> {
    const response = await apiClient.get<AuditLogStatsResponse>("/audit-logs/stats", { params });
    return response.data;
  },
};
