import { useQuery } from "@tanstack/react-query";
import { Button, Card, Col, Progress, Row, Space, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";

import { systemApi } from "../api/system";
import { roleLabels } from "../auth/rbac";
import { useAuthStore } from "../stores/authStore";

const capabilityCards = [
  {
    index: "01",
    title: "智能问答与诊断",
    description: "通过意图路由统一编排知识问答、质量规则、SQL 分析和历史案例检索。",
    accent: "cyan",
  },
  {
    index: "02",
    title: "在线混合检索",
    description: "融合 Qdrant 语义召回与 OpenSearch 关键词召回，并保留可追溯引用证据。",
    accent: "violet",
  },
  {
    index: "03",
    title: "质量运营闭环",
    description: "连接用户反馈、检索评估、Prompt 版本、节点耗时和模型用量。",
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
          <Typography.Text className="page-eyebrow">工业质量智能控制台</Typography.Text>
          <Typography.Title level={1}>
            欢迎回来，{user?.username}
          </Typography.Title>
          <Typography.Paragraph>
            在一个工作台中完成工业知识问答、设备异常排查、知识库维护、质量评估与运行监控。
          </Typography.Paragraph>
          <Space wrap>
            <Button type="primary" size="large" onClick={() => navigate("/chat")}>
              开始智能问答
            </Button>
            <Button size="large" onClick={() => navigate("/knowledge-base")}>
              管理知识库
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
                <Typography.Text className="page-eyebrow">核心能力链路</Typography.Text>
                <Typography.Title level={4}>企业 RAG 运行控制面</Typography.Title>
              </div>
              <Tag color="success" bordered={false}>已接入</Tag>
            </div>
            <div className="phase-list">
              <div className="phase-item phase-item--done">
                <span>01</span><div><strong>身份与访问控制</strong><small>JWT 登录、角色权限和操作审计</small></div><b>已接入</b>
              </div>
              <div className="phase-item phase-item--done">
                <span>02</span><div><strong>Agentic RAG 工作流</strong><small>意图路由、查询改写、工具调用和证据判断</small></div><b>已接入</b>
              </div>
              <div className="phase-item phase-item--done">
                <span>03</span><div><strong>知识库管理</strong><small>上传、列表、索引状态与生命周期</small></div><b>已完成</b>
              </div>
              <div className="phase-item phase-item--done">
                <span>04</span><div><strong>评估与反馈闭环</strong><small>反馈、Recall、MRR、生成质量与回归对比</small></div><b>已接入</b>
              </div>
              <div className="phase-item phase-item--done">
                <span>05</span><div><strong>运行可观测性</strong><small>请求追踪、节点延迟、Token、成本和健康检查</small></div><b>已接入</b>
              </div>
              <div className="phase-item phase-item--active">
                <span>06</span><div><strong>安全发布基线</strong><small>自动化测试、容器健康和发布环境校验</small></div><b>已接入</b>
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
              <Progress percent={100} showInfo={false} strokeColor="#0f766e" trailColor="#e7ecef" />
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
