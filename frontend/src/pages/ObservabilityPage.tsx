import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Progress,
  Row,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  type TableColumnsType,
} from "antd";

import { getApiErrorMessage } from "../api/client";
import { observabilityApi } from "../api/observability";
import type { ModelUsageItem, RetrievalUsageItem } from "../api/types";
import { MetricSparkline } from "../features/observability/MetricSparkline";
import { RequestDetailsDrawer } from "../features/observability/RequestDetailsDrawer";
import {
  buildAnalyticsRange,
  formatCompactNumber,
  formatCost,
  percentage,
} from "../features/observability/presentation";

const rangeOptions = [
  { label: "24 小时", value: 1 },
  { label: "7 天", value: 7 },
  { label: "30 天", value: 30 },
];

export function ObservabilityPage() {
  const queryClient = useQueryClient();
  const [days, setDays] = useState(7);
  const [requestInput, setRequestInput] = useState("");
  const [lookupRequestId, setLookupRequestId] = useState<string | null>(null);
  const range = useMemo(() => buildAnalyticsRange(days), [days]);
  const queryOptions = { staleTime: 30_000 };

  const overview = useQuery({
    queryKey: ["observability", "overview", days],
    queryFn: () => observabilityApi.overview(range),
    ...queryOptions,
  });
  const timeseries = useQuery({
    queryKey: ["observability", "timeseries", days],
    queryFn: () => observabilityApi.timeseries(range, days === 1 ? "hour" : "day"),
    ...queryOptions,
  });
  const models = useQuery({
    queryKey: ["observability", "models", days],
    queryFn: () => observabilityApi.models(range),
    ...queryOptions,
  });
  const intents = useQuery({
    queryKey: ["observability", "intents", days],
    queryFn: () => observabilityApi.intents(range),
    ...queryOptions,
  });
  const retrieval = useQuery({
    queryKey: ["observability", "retrieval", days],
    queryFn: () => observabilityApi.retrieval(range),
    ...queryOptions,
  });
  const requestDetails = useQuery({
    queryKey: ["observability", "request", lookupRequestId],
    queryFn: () => observabilityApi.requestDetails(lookupRequestId as string),
    enabled: Boolean(lookupRequestId),
    retry: false,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["observability"] });
  const lookup = () => {
    const requestId = requestInput.trim();
    if (requestId) {
      setLookupRequestId(requestId);
    }
  };

  const modelColumns: TableColumnsType<ModelUsageItem> = [
    { title: "Provider", dataIndex: "provider", width: 100 },
    { title: "Model", dataIndex: "model", width: 170, ellipsis: true },
    { title: "Operation", dataIndex: "operation", width: 130 },
    { title: "Calls", dataIndex: "call_count", width: 80, align: "right" },
    { title: "Failed", dataIndex: "failed_count", width: 80, align: "right" },
    { title: "Avg latency", dataIndex: "avg_latency_ms", width: 110, render: (value) => `${Number(value).toFixed(0)} ms` },
    { title: "Tokens", dataIndex: "total_tokens", width: 100, render: formatCompactNumber },
    { title: "Cost", dataIndex: "calculated_cost", width: 100, render: (value, row) => formatCost(value, row.currency) },
  ];
  const retrievalColumns: TableColumnsType<RetrievalUsageItem> = [
    { title: "模式", dataIndex: "retrieval_mode", width: 135, render: (value) => <Tag bordered={false}>{value}</Tag> },
    { title: "请求", dataIndex: "request_count", width: 75, align: "right" },
    { title: "降级", dataIndex: "degraded_count", width: 75, align: "right" },
    { title: "失败", dataIndex: "failed_count", width: 75, align: "right" },
    { title: "总延迟", dataIndex: "avg_latency_ms", width: 100, render: (value) => `${Number(value).toFixed(0)} ms` },
    { title: "Qdrant", dataIndex: "avg_qdrant_latency_ms", width: 100, render: (value) => `${Number(value).toFixed(0)} ms` },
    { title: "OpenSearch", dataIndex: "avg_opensearch_latency_ms", width: 110, render: (value) => `${Number(value).toFixed(0)} ms` },
    { title: "返回数", dataIndex: "avg_returned_count", width: 80, render: (value) => Number(value).toFixed(1) },
  ];

  const data = overview.data;
  const series = timeseries.data?.items || [];
  const intentItems = intents.data?.items || [];
  const maxIntentRequests = Math.max(...intentItems.map((item) => item.request_count), 1);
  const hasError = overview.isError || timeseries.isError || models.isError || intents.isError || retrieval.isError;

  return (
    <div className="observability-page page-stack">
      <section className="observability-hero">
        <div>
          <Typography.Text className="page-eyebrow">RUNTIME INTELLIGENCE</Typography.Text>
          <Typography.Title level={2}>用量与可观测性</Typography.Title>
          <Typography.Paragraph>从请求、模型 Token、检索降级和延迟分位数观察 RAG 运行质量，并通过 request_id 下钻 AI 与 Retrieval Events。</Typography.Paragraph>
        </div>
        <Space wrap>
          <Segmented value={days} options={rangeOptions} onChange={(value) => setDays(Number(value))} />
          <Button loading={overview.isFetching} onClick={refresh}>刷新数据</Button>
        </Space>
      </section>

      {hasError && <Alert type="error" showIcon message="部分可观测性数据加载失败" description={getApiErrorMessage(overview.error || timeseries.error || models.error || intents.error || retrieval.error)} />}

      <Row gutter={[14, 14]}>
        <Col xs={12} xl={4}><Card className="obs-metric"><Statistic title="总请求" value={data?.total_requests || 0} /></Card></Col>
        <Col xs={12} xl={4}><Card className="obs-metric obs-metric--success"><Statistic title="成功率" value={(data?.success_rate || 0) * 100} precision={1} suffix="%" /></Card></Col>
        <Col xs={12} xl={4}><Card className="obs-metric"><Statistic title="P95 延迟" value={data?.p95_latency_ms || 0} precision={0} suffix="ms" /></Card></Col>
        <Col xs={12} xl={4}><Card className="obs-metric"><Statistic title="总 Token" value={formatCompactNumber(data?.total_tokens)} /></Card></Col>
        <Col xs={12} xl={4}><Card className="obs-metric"><Statistic title="估算成本" value={formatCost(data?.calculated_cost, data?.currency)} /></Card></Col>
        <Col xs={12} xl={4}><Card className={`obs-metric${data?.degraded_count ? " obs-metric--warning" : ""}`}><Statistic title="降级率" value={(data?.degraded_rate || 0) * 100} precision={1} suffix="%" /></Card></Col>
      </Row>

      <div className="observability-grid">
        <Card className="trend-card" bordered={false}>
          <div className="obs-card-heading"><div><Typography.Text className="panel-kicker">REQUEST TREND</Typography.Text><Typography.Title level={4}>请求量趋势</Typography.Title></div><Tag bordered={false}>{series.length} buckets</Tag></div>
          <MetricSparkline values={series.map((item) => item.request_count)} />
          <div className="trend-footer"><span><b>{series.reduce((sum, item) => sum + item.failed_count, 0)}</b>failed</span><span><b>{series.reduce((sum, item) => sum + item.degraded_count, 0)}</b>degraded</span><span><b>{formatCompactNumber(series.reduce((sum, item) => sum + item.total_tokens, 0))}</b>tokens</span></div>
        </Card>
        <Card className="trend-card" bordered={false}>
          <div className="obs-card-heading"><div><Typography.Text className="panel-kicker">LATENCY TREND</Typography.Text><Typography.Title level={4}>平均延迟趋势</Typography.Title></div><Tag bordered={false}>P95 {Number(data?.p95_latency_ms || 0).toFixed(0)} ms</Tag></div>
          <MetricSparkline values={series.map((item) => item.avg_latency_ms)} color="#7867a0" />
          <div className="trend-footer"><span><b>{Number(data?.avg_latency_ms || 0).toFixed(0)} ms</b>average</span><span><b>{data?.evidence_enough_count || 0}</b>evidence enough</span><span><b>{data?.failed_count || 0}</b>failed</span></div>
        </Card>
      </div>

      <div className="observability-grid observability-grid--bottom">
        <Card className="intent-card" bordered={false}>
          <div className="obs-card-heading"><div><Typography.Text className="panel-kicker">INTENT DISTRIBUTION</Typography.Text><Typography.Title level={4}>意图与用量</Typography.Title></div></div>
          <div className="intent-usage-bars">
            {intentItems.map((item) => (
              <div key={item.intent}>
                <span><b>{item.intent}</b><small>{item.request_count} requests · {item.failed_count} failed</small></span>
                <Progress percent={(item.request_count / maxIntentRequests) * 100} showInfo={false} strokeColor="#0a8f86" />
                <em>{Number(item.avg_latency_ms).toFixed(0)} ms</em>
              </div>
            ))}
            {!intentItems.length && <Typography.Text type="secondary">当前时间范围内暂无意图数据。</Typography.Text>}
          </div>
        </Card>

        <Card className="request-lookup-card" bordered={false}>
          <div className="obs-card-heading"><div><Typography.Text className="panel-kicker">REQUEST DRILLDOWN</Typography.Text><Typography.Title level={4}>请求追踪查询</Typography.Title></div></div>
          <Typography.Paragraph>粘贴聊天响应中的 request_id，查看请求汇总、AI 调用事件与检索事件。</Typography.Paragraph>
          <Input.Search
            value={requestInput}
            placeholder="request_id"
            enterButton="查询"
            loading={requestDetails.isFetching}
            onChange={(event) => setRequestInput(event.target.value)}
            onSearch={lookup}
          />
          {requestDetails.isError && <Alert type="error" showIcon message={getApiErrorMessage(requestDetails.error)} />}
          <div className="request-lookup-meta"><span>当前窗口 <b>{days === 1 ? "24H" : `${days}D`}</b></span><span>权限 <b>ADMIN / ENGINEER</b></span></div>
        </Card>
      </div>

      <Card className="observability-table-card" bordered={false}>
        <div className="obs-card-heading"><div><Typography.Text className="panel-kicker">MODEL USAGE</Typography.Text><Typography.Title level={4}>模型调用与成本</Typography.Title></div><span>{formatCost(data?.calculated_cost, data?.currency)} total</span></div>
        <Table rowKey={(row) => `${row.provider}-${row.model}-${row.operation}-${row.currency || "none"}`} columns={modelColumns} dataSource={models.data?.items || []} loading={models.isLoading} scroll={{ x: 900 }} pagination={false} />
      </Card>

      <Card className="observability-table-card" bordered={false}>
        <div className="obs-card-heading"><div><Typography.Text className="panel-kicker">RETRIEVAL RUNTIME</Typography.Text><Typography.Title level={4}>混合检索运行质量</Typography.Title></div><Tag color={data?.degraded_count ? "warning" : "success"} bordered={false}>{percentage(data?.degraded_rate)} degraded</Tag></div>
        <Table rowKey="retrieval_mode" columns={retrievalColumns} dataSource={retrieval.data?.items || []} loading={retrieval.isLoading} scroll={{ x: 900 }} pagination={false} />
      </Card>

      <RequestDetailsDrawer
        open={Boolean(lookupRequestId) && (requestDetails.isSuccess || requestDetails.isLoading)}
        loading={requestDetails.isLoading}
        details={requestDetails.data}
        onClose={() => setLookupRequestId(null)}
      />
    </div>
  );
}
