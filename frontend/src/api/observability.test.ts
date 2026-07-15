import { vi } from "vitest";

import { apiClient } from "./client";
import { observabilityApi } from "./observability";

describe("observabilityApi", () => {
  afterEach(() => vi.restoreAllMocks());

  it("passes the selected UTC analytics window", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: {} });
    const range = {
      startAt: "2026-07-01T00:00:00.000Z",
      endAt: "2026-07-08T00:00:00.000Z",
    };
    await observabilityApi.overview(range);
    expect(get).toHaveBeenCalledWith("/observability/analytics/overview", {
      params: { start_at: range.startAt, end_at: range.endAt },
    });
  });

  it("encodes request ids for drilldown", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: {} });
    await observabilityApi.requestDetails("request / 1");
    expect(get).toHaveBeenCalledWith("/observability/requests/request%20%2F%201");
  });
});
