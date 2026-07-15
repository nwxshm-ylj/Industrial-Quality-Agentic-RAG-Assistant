import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router-dom";

import { RequireAuth } from "../auth/RequireAuth";
import { RequireRole } from "../auth/RequireRole";

const AppShell = lazy(() =>
  import("../layout/AppShell").then((module) => ({ default: module.AppShell })),
);
const DashboardPage = lazy(() =>
  import("../pages/DashboardPage").then((module) => ({
    default: module.DashboardPage,
  })),
);
const ChatPage = lazy(() =>
  import("../pages/ChatPage").then((module) => ({ default: module.ChatPage })),
);
const KnowledgeBasePage = lazy(() =>
  import("../pages/KnowledgeBasePage").then((module) => ({
    default: module.KnowledgeBasePage,
  })),
);
const EvaluationPage = lazy(() =>
  import("../pages/EvaluationPage").then((module) => ({
    default: module.EvaluationPage,
  })),
);
const ObservabilityPage = lazy(() =>
  import("../pages/ObservabilityPage").then((module) => ({
    default: module.ObservabilityPage,
  })),
);
const SystemHealthPage = lazy(() =>
  import("../pages/SystemHealthPage").then((module) => ({
    default: module.SystemHealthPage,
  })),
);
const UserManagementPage = lazy(() =>
  import("../pages/UserManagementPage").then((module) => ({
    default: module.UserManagementPage,
  })),
);
const AuditLogsPage = lazy(() =>
  import("../pages/AuditLogsPage").then((module) => ({
    default: module.AuditLogsPage,
  })),
);
const LoginPage = lazy(() =>
  import("../pages/LoginPage").then((module) => ({ default: module.LoginPage })),
);
const ForbiddenPage = lazy(() =>
  import("../pages/ForbiddenPage").then((module) => ({
    default: module.ForbiddenPage,
  })),
);
const NotFoundPage = lazy(() =>
  import("../pages/NotFoundPage").then((module) => ({
    default: module.NotFoundPage,
  })),
);

function lazyElement(element: ReactNode) {
  return (
    <Suspense fallback={<div className="route-loading"><span />正在加载工作台</div>}>
      {element}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: lazyElement(<LoginPage />),
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: lazyElement(<AppShell />),
        children: [
          { index: true, element: lazyElement(<DashboardPage />) },
          {
            path: "chat",
            element: lazyElement(<ChatPage />),
          },
          {
            path: "knowledge-base",
            element: lazyElement(<KnowledgeBasePage />),
          },
          {
            element: <RequireRole roles={["admin", "engineer"]} />,
            children: [
              {
                path: "evaluation",
                element: lazyElement(<EvaluationPage />),
              },
              {
                path: "observability",
                element: lazyElement(<ObservabilityPage />),
              },
              {
                path: "system-health",
                element: lazyElement(<SystemHealthPage />),
              },
            ],
          },
          {
            element: <RequireRole roles={["admin"]} />,
            children: [
              {
                path: "admin/users",
                element: lazyElement(<UserManagementPage />),
              },
              {
                path: "admin/audit-logs",
                element: lazyElement(<AuditLogsPage />),
              },
            ],
          },
          { path: "forbidden", element: lazyElement(<ForbiddenPage />) },
          { path: "*", element: lazyElement(<NotFoundPage />) },
        ],
      },
    ],
  },
]);
