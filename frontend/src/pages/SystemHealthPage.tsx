import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Row, Tag, Typography } from "antd";

import { systemApi } from "../api/system";

const checkLabels: Record<string, string> = {
  postgresql: "PostgreSQL",
  qdrant: "Qdrant Vector Index",
  opensearch: "OpenSearch Keyword Index",
  model_configuration: "Model Configuration",
  prompt_registry: "Prompt Registry",
};

export function SystemHealthPage() {
  const readiness = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: systemApi.readiness,
    refetchInterval: 15_000,
    retry: false,
  });
  const data = readiness.data;
  const entries = Object.entries(data?.checks || {});

  return (
    <div className="health-page page-stack">
      <section className={`health-hero health-hero--${data?.status || "unknown"}`}>
        <div>
          <Typography.Text className="page-eyebrow">SERVICE READINESS</Typography.Text>
          <Typography.Title level={2}>系统健康状态</Typography.Title>
          <Typography.Paragraph>统一检查 API 核心依赖，不会触发真实收费 Embedding 调用。</Typography.Paragraph>
        </div>
        <div className="health-overall">
          <span />
          <div><strong>{data?.status?.toUpperCase() || "CHECKING"}</strong><small>刷新周期 15 秒</small></div>
          <Button onClick={() => readiness.refetch()} loading={readiness.isFetching}>立即刷新</Button>
        </div>
      </section>

      {readiness.isError && <Alert type="error" showIcon message="无法读取健康状态" description="请确认 FastAPI 服务和反向代理配置正常。" />}
      {data?.status === "degraded" && <Alert type="warning" showIcon message="系统处于降级状态" description="核心链路可用，但关键词检索等非关键依赖可能不可用。" />}
      {data?.status === "not_ready" && <Alert type="error" showIcon message="系统尚未就绪" description="至少一项关键依赖不可用，请根据下方 error_type 排查。" />}

      <Row gutter={[16, 16]}>
        {entries.map(([name, check]) => {
          const ready = check.status === "ready";
          return (
            <Col xs={24} md={12} xl={8} key={name}>
              <Card className={`health-check-card${ready ? " is-ready" : " is-unavailable"}`} bordered={false}>
                <div className="health-check-card__head"><span>{checkLabels[name] || name}</span><Tag color={ready ? "success" : "error"} bordered={false}>{check.status.toUpperCase()}</Tag></div>
                <Typography.Text>{check.error_type ? `错误类型：${check.error_type}` : "依赖连接与配置检查通过"}</Typography.Text>
                {check.release_id && <div className="health-check-card__meta"><span>Release</span><strong>{check.release_id}</strong></div>}
                {check.channel && <div className="health-check-card__meta"><span>Channel</span><strong>{check.channel}</strong></div>}
              </Card>
            </Col>
          );
        })}
      </Row>
    </div>
  );
}
