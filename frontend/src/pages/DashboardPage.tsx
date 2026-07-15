import { useQuery } from "@tanstack/react-query";
import { Button, Card, Col, Progress, Row, Space, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";

import { systemApi } from "../api/system";
import { roleLabels } from "../auth/rbac";
import { useAuthStore } from "../stores/authStore";

const capabilityCards = [
  {
    index: "01",
    title: "Agentic RAG",
    description: "多意图路由、对话记忆、规则、SQL 与历史案例统一编排。",
    accent: "cyan",
  },
  {
    index: "02",
    title: "Online Hybrid Search",
    description: "Qdrant 向量召回与 OpenSearch 关键词召回经 RRF 融合。",
    accent: "violet",
  },
  {
    index: "03",
    title: "Quality Feedback Loop",
    description: "反馈、检索指标、Prompt 版本与运行用量形成质量闭环。",
    accent: "amber",
  },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const health = useQuery({
    queryKey: ["system", "liveness"],
    queryFn: systemApi.liveness,
    retry: 1,
    refetchInterval: 15_000,
  });

  return (
    <div className="dashboard-page page-stack">
      <section className="welcome-panel">
        <div className="welcome-panel__copy">
            <Typography.Text className="page-eyebrow">PHASE 5 ENTERPRISE CONTROL</Typography.Text>
          <Typography.Title level={1}>
            欢迎回来，{user?.username}
          </Typography.Title>
          <Typography.Paragraph>
            React 企业工作台已形成问答、知识入库、质量评估、运行可观测性与安全管理的完整控制面。
          </Typography.Paragraph>
          <Space wrap>
            <Button type="primary" size="large" onClick={() => navigate("/chat")}>
              查看 RAG 工作区
            </Button>
            <Button size="large" onClick={() => navigate("/knowledge-base")}>
              查看知识库入口
            </Button>
          </Space>
        </div>
        <div className="welcome-panel__telemetry">
          <div className="telemetry-ring">
            <div>
              <strong>{health.isSuccess ? "LIVE" : "WAIT"}</strong>
              <span>API STATUS</span>
            </div>
          </div>
          <div className="telemetry-meta">
            <span><i className={health.isSuccess ? "is-online" : "is-offline"} />FastAPI</span>
            <span><i className="is-online" />React Console</span>
            <span><i className="is-online" />RBAC Guard</span>
          </div>
        </div>
      </section>

      <Row gutter={[18, 18]}>
        {capabilityCards.map((item) => (
          <Col xs={24} lg={8} key={item.index}>
            <Card className={`capability-card capability-card--${item.accent}`} bordered={false}>
              <span className="capability-card__index">{item.index}</span>
              <Typography.Title level={4}>{item.title}</Typography.Title>
              <Typography.Paragraph>{item.description}</Typography.Paragraph>
              <span className="capability-card__line" />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[18, 18]}>
        <Col xs={24} xl={15}>
          <Card className="foundation-card" bordered={false}>
            <div className="section-heading">
              <div>
                <Typography.Text className="page-eyebrow">DELIVERY STATUS</Typography.Text>
                <Typography.Title level={4}>React 前端迁移路径</Typography.Title>
              </div>
              <Tag color="processing" bordered={false}>PHASE 5</Tag>
            </div>
            <div className="phase-list">
              <div className="phase-item phase-item--done">
                <span>01</span><div><strong>基础工程</strong><small>认证、API Client、Layout、RBAC、Docker</small></div><b>已完成</b>
              </div>
              <div className="phase-item phase-item--done">
                <span>02</span><div><strong>RAG 对话工作台</strong><small>多轮会话、引用、执行详情与响应兼容</small></div><b>已完成</b>
              </div>
              <div className="phase-item phase-item--done">
                <span>03</span><div><strong>知识库管理</strong><small>上传、列表、索引状态与生命周期</small></div><b>已完成</b>
              </div>
              <div className="phase-item phase-item--done">
                <span>04</span><div><strong>评估与可观测性</strong><small>反馈、Recall/MRR、Token、成本与请求追踪</small></div><b>已实现</b>
              </div>
              <div className="phase-item phase-item--active">
                <span>05</span><div><strong>企业管理控制台</strong><small>用户、审计、健康检查与发布验收</small></div><b>已实现</b>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card className="identity-card" bordered={false}>
            <Typography.Text className="page-eyebrow">ACTIVE IDENTITY</Typography.Text>
            <div className="identity-card__avatar">{user?.username.slice(0, 1).toUpperCase()}</div>
            <Typography.Title level={3}>{user?.username}</Typography.Title>
            <Tag className={`role-tag role-tag--${user?.role}`} bordered={false}>
              {user?.role ? roleLabels[user.role] : "未知角色"}
            </Tag>
            <div className="identity-card__progress">
              <span><strong>会话级认证</strong><small>Bearer Token / sessionStorage</small></span>
              <Progress percent={100} showInfo={false} strokeColor="#24d1c0" trailColor="#e8eef3" />
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
