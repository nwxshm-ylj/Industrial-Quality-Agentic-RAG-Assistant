import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";

import { App } from "./App";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { industrialTheme } from "./design/antdTheme";
import "./styles/global.css";
import "./styles/design-system.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfigProvider locale={zhCN} theme={industrialTheme}>
      <AntdApp>
        <QueryClientProvider client={queryClient}>
          <AppErrorBoundary><App /></AppErrorBoundary>
        </QueryClientProvider>
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
);
