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
          colorPrimary: "#0f766e",
          colorPrimaryHover: "#0d8a80",
          colorPrimaryActive: "#0b5f59",
          colorInfo: "#356b8c",
          colorSuccess: "#1b7f5c",
          colorWarning: "#a86416",
          colorError: "#b64040",
          colorText: "#172b3a",
          colorTextSecondary: "#5f7180",
          colorBgLayout: "#eef2f4",
          colorBgContainer: "#ffffff",
          colorBgElevated: "#ffffff",
          colorBorder: "#d7e0e5",
          colorBorderSecondary: "#e7ecef",
          borderRadius: 10,
          borderRadiusLG: 16,
          fontFamily:
            "Inter, 'Noto Sans SC', 'Microsoft YaHei', system-ui, sans-serif",
        },
        components: {
          Button: {
            controlHeightLG: 46,
            fontWeight: 600,
            primaryShadow: "none",
          },
          Card: { headerBg: "#ffffff" },
          Input: { controlHeightLG: 48 },
          Menu: { itemBorderRadius: 8, itemHeight: 44 },
          Table: { headerBg: "#f5f7f8", headerColor: "#526674" },
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
