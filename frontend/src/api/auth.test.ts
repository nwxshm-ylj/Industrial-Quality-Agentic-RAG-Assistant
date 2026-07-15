import { vi } from "vitest";

import { apiClient } from "./client";
import { authApi } from "./auth";

describe("authApi administration", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists users through the admin endpoint", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: [] });
    await authApi.listUsers();
    expect(get).toHaveBeenCalledWith("/auth/users");
  });

  it("creates users without transforming credentials", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    const payload = { username: "engineer_a", password: "password123", role: "engineer" as const };
    await authApi.createUser(payload);
    expect(post).toHaveBeenCalledWith("/auth/users", payload);
  });
});
