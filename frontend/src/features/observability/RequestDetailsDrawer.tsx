import { Descriptions, Drawer, Empty, Tabs, Tag, Typography } from "antd";

import type { RequestUsageDetailsResponse } from "../../api/types";

interface RequestDetailsDrawerProps {
  open: boolean;
  loading: boolean;
  details?: RequestUsageDetailsResponse;
  onClose: () => void;
}

function json(value: unknown) {
  return <pre className="json-viewer request-json">{JSON.stringify(value, null, 2)}</pre>;
}

export function RequestDetailsDrawer({ open, loading, details, onClose }: RequestDetailsDrawerProps) {
  const request = details?.request || {};
  return (
    <Drawer
      width={680}
      open={open}
      loading={loading}
      onClose={onClose}
      title={(
        <div><Typography.Text className="panel-kicker">REQUEST DRILLDOWN</Typography.Text><Typography.Title level={4}>请求级用量与 Trace</Typography.Title></div>
      )}
    >
      {details ? (
        <div className="request-detail-stack">
          <Descriptions column={2} bordered size="small" colon={false}>
            <Descriptions.Item label="Request ID" span={2}>{String(request.request_id || "--")}</Descriptions.Item>
            <Descriptions.Item label="Trace ID" span={2}>{String(request.trace_id || "--")}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag bordered={false}>{String(request.status || "--")}</Tag></Descriptions.Item>
            <Descriptions.Item label="意图">{String(request.intent || "--")}</Descriptions.Item>
            <Descriptions.Item label="总延迟">{String(request.total_latency_ms || 0)} ms</Descriptions.Item>
            <Descriptions.Item label="总 Token">{String(request.total_tokens || 0)}</Descriptions.Item>
            <Descriptions.Item label="检索模式">{String(request.retrieval_mode || "--")}</Descriptions.Item>
            <Descriptions.Item label="是否降级">{request.degraded ? "YES" : "NO"}</Descriptions.Item>
          </Descriptions>
          <Tabs items={[
            { key: "request", label: "请求", children: json(request) },
            { key: "ai", label: `AI Events ${details.ai_events?.length || 0}`, children: json(details.ai_events || []) },
            { key: "retrieval", label: `Retrieval Events ${details.retrieval_events?.length || 0}`, children: json(details.retrieval_events || []) },
          ]} />
        </div>
      ) : <Empty description="输入 request_id 查看详情" />}
    </Drawer>
  );
}
