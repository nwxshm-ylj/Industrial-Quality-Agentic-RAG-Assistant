import { useAuthStore } from "./authStore";

describe("auth store", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
  });

  it("stores an authenticated session and role", () => {
    useAuthStore.getState().setSession({
      access_token: "test-token",
      token_type: "bearer",
      user: {
        username: "engineer-test",
        role: "engineer",
        is_active: true,
      },
    });

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.accessToken).toBe("test-token");
    expect(state.hasRole("admin", "engineer")).toBe(true);
    expect(state.hasRole("admin")).toBe(false);
  });

  it("clears all sensitive session state on logout", () => {
    useAuthStore.getState().setSession({
      access_token: "test-token",
      token_type: "bearer",
      user: { username: "admin", role: "admin", is_active: true },
    });
    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
  });
});
