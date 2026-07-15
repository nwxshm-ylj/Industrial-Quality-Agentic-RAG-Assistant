import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";

import { App } from "./App";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import "./styles/global.css";

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
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#0a8f86",
          colorInfo: "#0a8f86",
          colorSuccess: "#158765",
          colorWarning: "#c77b19",
          colorError: "#c64949",
          colorText: "#132333",
          colorTextSecondary: "#627184",
          colorBgLayout: "#f3f6f8",
          borderRadius: 10,
          borderRadiusLG: 16,
          fontFamily:
            "Inter, 'Noto Sans SC', 'Microsoft YaHei', system-ui, sans-serif",
        },
        components: {
          Button: { controlHeightLG: 46, fontWeight: 600 },
          Input: { controlHeightLG: 48 },
          Menu: { itemBorderRadius: 8, itemHeight: 44 },
        },
      }}
    >
      <AntdApp>
        <QueryClientProvider client={queryClient}>
          <AppErrorBoundary><App /></AppErrorBoundary>
        </QueryClientProvider>
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
);
