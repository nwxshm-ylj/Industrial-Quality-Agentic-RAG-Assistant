import type { Page, Route } from "@playwright/test";

export type MockRole = "admin" | "engineer" | "viewer";

interface MockUser {
  username: string;
  role: MockRole;
  is_active: boolean;
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export async function installMockApi(page: Page, loginRole: MockRole = "admin") {
  const users: MockUser[] = [
    { username: "admin", role: "admin", is_active: true },
    { username: "quality_engineer", role: "engineer", is_active: true },
    { username: "readonly_user", role: "viewer", is_active: true },
  ];

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === "/health/live") {
      return json(route, { status: "alive" });
    }
    if (path === "/health/ready") {
      return json(route, {
        status: "ready",
        checks: {
          postgresql: { status: "ready" },
          qdrant: { status: "ready" },
          opensearch: { status: "ready" },
          model_configuration: { status: "ready" },
          prompt_registry: { status: "ready", release_id: "stable-v1", channel: "stable" },
        },
      });
    }
    if (path === "/api/v1/auth/login" && request.method() === "POST") {
      const payload = request.postDataJSON() as { username: string };
      return json(route, {
        access_token: `mock-token-${loginRole}`,
        token_type: "bearer",
        user: { username: payload.username, role: loginRole, is_active: true },
      });
    }
    if (path === "/api/v1/auth/users" && request.method() === "GET") {
      return json(route, users);
    }
    if (path === "/api/v1/auth/users" && request.method() === "POST") {
      const payload = request.postDataJSON() as { username: string; role: MockRole };
      const created = { username: payload.username, role: payload.role, is_active: true };
      users.push(created);
      return json(route, created);
    }
    if (path === "/api/v1/graph-chat" && request.method() === "POST") {
      const payload = request.postDataJSON() as { question: string; session_id: string };
      return json(route, {
        question: payload.question,
        answer: "建议优先检查相机曝光、轮毂型号配置和识别区域遮挡。",
        intent: "fault_diagnosis",
        rewritten_query: payload.question,
        contexts: [],
        citations: [],
        evidence_score: 0.88,
        evidence_enough: true,
        retry_count: 0,
        session_id: payload.session_id,
        request_id: "request-e2e-001",
        memory_messages: [],
        metadata: {
          intent: "fault_diagnosis",
          total_latency_ms: 128,
          degraded: false,
          retrieval_mode: "hybrid",
        },
      });
    }
    if (path === "/api/v1/feedback" && request.method() === "POST") {
      return json(route, { id: 1, status: "success", message: "反馈已记录" });
    }
    if (path === "/api/v1/audit-logs/stats") {
      return json(route, {
        total: 12,
        success_count: 9,
        denied_count: 2,
        failed_count: 1,
        top_actions: [{ action: "graph_chat", count: 5 }],
      });
    }
    if (path === "/api/v1/audit-logs") {
      return json(route, {
        items: [{
          id: 1,
          request_id: "request-e2e-001",
          session_id: "session-e2e",
          username: "admin",
          role: "admin",
          action: "graph_chat",
          resource_type: "chat",
          resource_id: "request-e2e-001",
          status: "success",
          detail: "E2E audit fixture",
          created_at: "2026-07-15T08:00:00Z",
        }],
        total: 1,
        limit: 20,
        offset: 0,
      });
    }
    return route.continue();
  });
}

export async function login(page: Page, role: MockRole) {
  await installMockApi(page, role);
  await page.goto("/login");
  await page.getByLabel("用户名").fill(`${role}_user`);
  await page.getByLabel("密码").fill("password123");
  await page.getByRole("button", { name: "进入工作台" }).click();
  await page.getByRole("heading", { name: new RegExp(`欢迎回来，${role}_user`) }).waitFor();
}
