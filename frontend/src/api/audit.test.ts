import { vi } from "vitest";

import { apiClient } from "./client";
import { auditApi } from "./audit";

describe("auditApi", () => {
  afterEach(() => vi.restoreAllMocks());

  it("keeps audit filters server-side", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: { items: [], total: 0 } });
    const params = { username: "admin", status: "denied", limit: 20, offset: 20 };
    await auditApi.list(params);
    expect(get).toHaveBeenCalledWith("/audit-logs", { params });
  });

  it("queries aggregate statistics for a selected window", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: {} });
    const params = { start_at: "2026-07-01T00:00:00Z", end_at: "2026-07-08T00:00:00Z" };
    await auditApi.stats(params);
    expect(get).toHaveBeenCalledWith("/audit-logs/stats", { params });
  });
});
