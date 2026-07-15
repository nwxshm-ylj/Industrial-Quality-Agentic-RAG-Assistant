import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  Space,
  Tag,
  Typography,
} from "antd";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/auth";
import { getApiErrorMessage } from "../api/client";
import { systemApi } from "../api/system";
import type { LoginRequest } from "../api/types";
import { BrandMark } from "../components/BrandMark";
import { useAuthStore } from "../stores/authStore";

export function LoginPage() {
  const [form] = Form.useForm<LoginRequest>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loginError, setLoginError] = useState<string | null>(null);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const setSession = useAuthStore((state) => state.setSession);

  const returnTo = useMemo(() => {
    const candidate = searchParams.get("returnTo");
    return candidate?.startsWith("/") && !candidate.startsWith("//")
      ? candidate
      : "/";
  }, [searchParams]);

  const healthQuery = useQuery({
    queryKey: ["system", "liveness"],
    queryFn: systemApi.liveness,
    retry: 1,
    refetchInterval: 15_000,
  });

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (response) => {
      setSession(response);
      navigate(returnTo, { replace: true });
    },
    onError: (error) => setLoginError(getApiErrorMessage(error)),
  });

  useEffect(() => {
    setLoginError(null);
  }, [form]);

  if (isAuthenticated) {
    return <Navigate to={returnTo} replace />;
  }

  return (
    <main className="login-page">
      <section className="login-story" aria-label="产品介绍">
        <div className="login-story__grid" />
        <div className="login-story__content">
          <BrandMark />
          <div className="login-story__hero">
            <span className="hero-index">01 / QUALITY INTELLIGENCE</span>
            <Typography.Title>
              让工业知识
              <br />
              成为可验证的决策依据
            </Typography.Title>
            <Typography.Paragraph>
              将 Agentic RAG、双路检索、质量规则、历史案例与运行观测整合为统一工作台。
            </Typography.Paragraph>
          </div>
          <div className="login-story__capabilities">
            <div><strong>Qdrant</strong><span>语义向量检索</span></div>
            <div><strong>OpenSearch</strong><span>工业关键词召回</span></div>
            <div><strong>LangGraph</strong><span>显式任务编排</span></div>
          </div>
        </div>
        <div className="login-story__footer">
          <span>Industrial Quality Agentic RAG</span>
          <span>Enterprise Reference Architecture</span>
        </div>
      </section>

      <section className="login-panel" aria-label="用户登录">
        <div className="login-panel__inner">
          <div className="login-panel__status">
            <Tag
              bordered={false}
              color={healthQuery.isSuccess ? "success" : "warning"}
            >
              <span className="status-dot" />
              {healthQuery.isSuccess ? "API ONLINE" : "API UNAVAILABLE"}
            </Tag>
            <span>React Console · Phase 1</span>
          </div>

          <div className="login-panel__heading">
            <Typography.Text className="page-eyebrow">SECURE ACCESS</Typography.Text>
            <Typography.Title level={2}>登录工业智能工作台</Typography.Title>
            <Typography.Paragraph>
              使用现有 FastAPI JWT 账号登录。所有访问仍由后端 RBAC 强制校验。
            </Typography.Paragraph>
          </div>

          {loginError && (
            <Alert
              className="login-alert"
              type="error"
              showIcon
              message="登录失败"
              description={loginError}
              closable
              onClose={() => setLoginError(null)}
            />
          )}

          <Form<LoginRequest>
            form={form}
            layout="vertical"
            requiredMark={false}
            onFinish={(values) => {
              setLoginError(null);
              loginMutation.mutate(values);
            }}
          >
            <Form.Item
              label="用户名"
              name="username"
              rules={[{ required: true, message: "请输入用户名" }]}
            >
              <Input size="large" autoComplete="username" placeholder="例如：admin" />
            </Form.Item>
            <Form.Item
              label="密码"
              name="password"
              rules={[{ required: true, message: "请输入密码" }]}
            >
              <Input.Password
                size="large"
                autoComplete="current-password"
                placeholder="请输入登录密码"
              />
            </Form.Item>
            <div className="login-form__options">
              <Checkbox disabled>保持登录</Checkbox>
              <Typography.Text type="secondary">Token 仅保存于当前浏览器会话</Typography.Text>
            </div>
            <Button
              className="login-submit"
              size="large"
              type="primary"
              htmlType="submit"
              loading={loginMutation.isPending}
              block
            >
              进入工作台
            </Button>
          </Form>

          <div className="login-panel__demo">
            <Space direction="vertical" size={4}>
              <Typography.Text strong>演示环境默认账号</Typography.Text>
              <Typography.Text code>admin / admin123</Typography.Text>
              <Typography.Text type="secondary">
                生产部署必须修改默认密码与 JWT_SECRET_KEY。
              </Typography.Text>
            </Space>
          </div>
        </div>
      </section>
    </main>
  );
}
