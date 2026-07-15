import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  Input,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  type TableColumnsType,
} from "antd";

import { auditApi } from "../api/audit";
import type { AuditLogItem } from "../api/types";
import { buildAnalyticsRange } from "../features/observability/presentation";
import { formatDocumentDate } from "../features/knowledge-base/presentation";

const statusColors: Record<string, string> = {
  success: "success",
  denied: "warning",
  failed: "error",
  error: "error",
  invalid: "error",
};

export function AuditLogsPage() {
  const [days, setDays] = useState(7);
  const [username, setUsername] = useState("");
  const [action, setAction] = useState("");
  const [status, setStatus] = useState<string | undefined>();
  const [requestId, setRequestId] = useState("");
  const [filters, setFilters] = useState({ username: "", action: "", status: undefined as string | undefined, requestId: "" });
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const range = useMemo(() => buildAnalyticsRange(days), [days]);

  const logs = useQuery({
    queryKey: ["admin", "audit", "list", days, filters, page],
    queryFn: () => auditApi.list({
      username: filters.username || undefined,
      action: filters.action || undefined,
      status: filters.status,
      request_id: filters.requestId || undefined,
      start_at: range.startAt,
      end_at: range.endAt,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }),
  });
  const stats = useQuery({
    queryKey: ["admin", "audit", "stats", days],
    queryFn: () => auditApi.stats({ start_at: range.startAt, end_at: range.endAt }),
  });

  const applyFilters = () => {
    setPage(1);
    setFilters({
      username: username.trim(),
      action: action.trim(),
      status,
      requestId: requestId.trim(),
    });
  };
  const clearFilters = () => {
    setUsername("");
    setAction("");
    setStatus(undefined);
    setRequestId("");
    setPage(1);
    setFilters({ username: "", action: "", status: undefined, requestId: "" });
  };

  const columns: TableColumnsType<AuditLogItem> = [
    { title: "时间", dataIndex: "created_at", width: 160, render: formatDocumentDate },
    { title: "用户", dataIndex: "username", width: 110, render: (value) => value || "anonymous" },
    { title: "角色", dataIndex: "role", width: 90, render: (value) => value || "--" },
    { title: "Action", dataIndex: "action", width: 190, ellipsis: true },
    { title: "状态", dataIndex: "status", width: 95, render: (value: string) => <Tag color={statusColors[value] || "default"} bordered={false}>{value || "--"}</Tag> },
    { title: "资源", key: "resource", width: 210, ellipsis: true, render: (_, row) => [row.resource_type, row.resource_id].filter(Boolean).join(" / ") || "--" },
    { title: "Request ID", dataIndex: "request_id", width: 220, ellipsis: true, render: (value) => value || "--" },
    { title: "详情", dataIndex: "detail", width: 260, ellipsis: true, render: (value) => value || "--" },
  ];

  return (
    <div className="admin-page page-stack">
      <section className="admin-hero">
        <div>
          <Typography.Text className="page-eyebrow">SECURITY AUDIT TRAIL</Typography.Text>
          <Typography.Title level={2}>操作审计日志</Typography.Title>
          <Typography.Paragraph>按身份、动作、状态和 request_id 追踪关键操作与权限拒绝事件。</Typography.Paragraph>
        </div>
        <Segmented value={days} onChange={(value) => { setDays(Number(value)); setPage(1); }} options={[{ label: "24 小时", value: 1 }, { label: "7 天", value: 7 }, { label: "30 天", value: 30 }]} />
      </section>

      <Row gutter={[14, 14]}>
        <Col xs={12} xl={6}><Card className="admin-metric"><Statistic title="审计事件" value={stats.data?.total || 0} /></Card></Col>
        <Col xs={12} xl={6}><Card className="admin-metric"><Statistic title="成功" value={stats.data?.success_count || 0} /></Card></Col>
        <Col xs={12} xl={6}><Card className="admin-metric"><Statistic title="权限拒绝" value={stats.data?.denied_count || 0} /></Card></Col>
        <Col xs={12} xl={6}><Card className="admin-metric"><Statistic title="失败 / 无效" value={stats.data?.failed_count || 0} /></Card></Col>
      </Row>

      <Card className="audit-filter-card" bordered={false}>
        <Space wrap>
          <Input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="用户名" allowClear />
          <Input value={action} onChange={(event) => setAction(event.target.value)} placeholder="Action，例如 graph_chat" allowClear />
          <Select value={status} onChange={setStatus} allowClear placeholder="状态" style={{ width: 145 }} options={["success", "denied", "failed", "invalid"].map((value) => ({ value, label: value }))} />
          <Input value={requestId} onChange={(event) => setRequestId(event.target.value)} placeholder="Request ID" allowClear className="audit-request-filter" />
          <Button type="primary" onClick={applyFilters}>查询</Button>
          <Button onClick={clearFilters}>清空</Button>
        </Space>
      </Card>

      <Card className="admin-table-card" bordered={false}>
        <div className="section-heading">
          <div><Typography.Text className="panel-kicker">IMMUTABLE OPERATIONS</Typography.Text><Typography.Title level={4}>事件明细</Typography.Title></div>
          <div className="top-actions">{stats.data?.top_actions.slice(0, 4).map((item) => <Tag key={item.action}>{item.action} · {item.count}</Tag>)}</div>
        </div>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={logs.data?.items || []}
          loading={logs.isLoading}
          scroll={{ x: 1350 }}
          pagination={{
            current: page,
            pageSize,
            total: logs.data?.total || 0,
            showSizeChanger: false,
            onChange: setPage,
          }}
        />
      </Card>
    </div>
  );
}
