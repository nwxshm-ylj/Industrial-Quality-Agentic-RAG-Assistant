import {
  Alert,
  Collapse,
  Descriptions,
  Empty,
  Space,
  Tabs,
  Tag,
  Typography,
  type CollapseProps,
  type TabsProps,
} from "antd";

import type {
  ChatProgressEvent,
  DiagnosticContext,
  RequestDiagnosticSnapshot,
} from "../../api/types";
import {
  diagnosticStatusColor,
  diagnosticStatusLabel,
} from "./diagnostics";

interface DiagnosticSnapshotViewProps {
  snapshot: RequestDiagnosticSnapshot;
  aiEvents?: Array<Record<string, unknown>>;
  retrievalEvents?: Array<Record<string, unknown>>;
  limitations?: string[];
  workflowEvents?: ChatProgressEvent[];
}

function json(value: unknown) {
  return <pre className="json-viewer request-json">{JSON.stringify(value, null, 2)}</pre>;
}

function contextTitle(item: DiagnosticContext, index: number): string {
  return item.source || item.doc_id || item.chunk_id || `证据 ${index + 1}`;
}

function ContextList({ items, emptyText }: { items: DiagnosticContext[]; emptyText: string }) {
  if (!items.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />;
  }
  return (
    <div className="diagnostic-context-list">
      {items.map((item, index) => (
        <article key={`${item.chunk_id || item.doc_id || "context"}-${index}`}>
          <header>
            <span>{String(item.rank || index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{contextTitle(item, index)}</strong>
              <small>
                {item.chunk_id || "--"}
                {item.page_number != null ? ` · page ${item.page_number}` : ""}
              </small>
            </div>
            <Tag bordered={false}>{item.retrieval_source || item.final_score_type || "context"}</Tag>
          </header>
          {item.evidence_chunk_ids?.length ? (
            <div className="diagnostic-bundle">
              <b>证据包</b>
              {item.evidence_chunk_ids.map((chunkId) => <code key={chunkId}>{chunkId}</code>)}
            </div>
          ) : null}
          {item.text_excerpt ? <p>{item.text_excerpt}</p> : (
            <Typography.Text type="secondary">历史正文未保留，仅显示结构化标识。</Typography.Text>
          )}
        </article>
      ))}
    </div>
  );
}

function ChecksTab({ snapshot, limitations = [] }: DiagnosticSnapshotViewProps) {
  const failureCount = snapshot.checks.filter((item) => item.status === "fail").length;
  const warningCount = snapshot.checks.filter((item) => item.status === "warning").length;
  return (
    <div className="diagnostic-checks">
      {limitations.map((item) => (
        <Alert key={item} type="info" showIcon message={item} />
      ))}
      <div className="diagnostic-summary">
        <span><b>{failureCount}</b>异常</span>
        <span><b>{warningCount}</b>关注</span>
        <span><b>{snapshot.checks.length}</b>检查项</span>
      </div>
      {snapshot.checks.map((item) => (
        <article key={item.code} className={`diagnostic-check diagnostic-check--${item.status}`}>
          <div>
            <Tag color={diagnosticStatusColor(item.status)} bordered={false}>
              {diagnosticStatusLabel(item.status)}
            </Tag>
            <code>{item.stage}</code>
          </div>
          <strong>{item.title}</strong>
          <p>{item.detail}</p>
        </article>
      ))}
    </div>
  );
}

function PipelineTab({ snapshot, retrievalEvents = [] }: DiagnosticSnapshotViewProps) {
  const candidateItems: CollapseProps["items"] = Object.entries(
    snapshot.retrieval.candidates || {},
  ).filter(([, items]) => Array.isArray(items)).map(([stage, items]) => ({
    key: stage,
    label: `${stage} (${items.length})`,
    children: <ContextList items={items} emptyText="该阶段没有候选" />,
  }));
  const routing = snapshot.routing || {};
  const metadata = snapshot.retrieval.metadata || {};
  const workflowEvents = snapshot.workflow_events || [];
  return (
    <div className="diagnostic-pipeline">
      <Descriptions bordered size="small" column={2} colon={false}>
        <Descriptions.Item label="意图">{String(routing.intent || "--")}</Descriptions.Item>
        <Descriptions.Item label="任务模式">{String(routing.task_mode || "--")}</Descriptions.Item>
        <Descriptions.Item label="请求模式">{String(routing.requested_retrieval_mode || "--")}</Descriptions.Item>
        <Descriptions.Item label="实际检索">{String(routing.retrieval_mode || "--")}</Descriptions.Item>
        <Descriptions.Item label="融合策略">{String(metadata.fusion_strategy || "--")}</Descriptions.Item>
        <Descriptions.Item label="降级">{metadata.degraded ? "YES" : "NO"}</Descriptions.Item>
      </Descriptions>
      {workflowEvents.length ? (
        <div className="diagnostic-workflow-events">
          {workflowEvents.filter((event) => event.status !== "running").map((event, index) => (
            <span key={`${event.node_name}-${event.status}-${index}`}>
              <i />
              <b>{event.label}</b>
              <small>{event.latency_ms != null ? `${event.latency_ms.toFixed(0)} ms` : event.status}</small>
            </span>
          ))}
        </div>
      ) : null}
      {candidateItems.length ? (
        <Collapse items={candidateItems} defaultActiveKey={["final"]} />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前回答没有持久化候选阶段；可查看最终上下文" />
      )}
      {retrievalEvents.length ? (
        <Collapse items={[{
          key: "events",
          label: `Retrieval Events (${retrievalEvents.length})`,
          children: json(retrievalEvents),
        }]} />
      ) : null}
    </div>
  );
}

function EvidenceTab({ snapshot }: DiagnosticSnapshotViewProps) {
  const contextTitle = snapshot.schema_version.startsWith("local")
    ? "当前响应携带的检索上下文"
    : "生成实际使用的上下文";
  return (
    <div className="diagnostic-evidence">
      <Typography.Title level={5}>{contextTitle}</Typography.Title>
      {snapshot.schema_version.startsWith("local") && (
        <Alert type="info" showIcon message="当前响应未单独暴露生成上下文，实际使用范围以服务端诊断快照为准。" />
      )}
      <ContextList items={snapshot.generation.contexts || []} emptyText="没有记录生成上下文" />
      <Typography.Title level={5}>引用映射</Typography.Title>
      <ContextList items={snapshot.generation.citations || []} emptyText="没有引用映射" />
      {snapshot.generation.answer_excerpt ? (
        <section className="diagnostic-answer">
          <Typography.Text className="panel-kicker">ANSWER SNAPSHOT</Typography.Text>
          <p>{snapshot.generation.answer_excerpt}</p>
        </section>
      ) : null}
    </div>
  );
}

export function DiagnosticSnapshotView(props: DiagnosticSnapshotViewProps) {
  const { snapshot, aiEvents = [] } = props;
  const items: TabsProps["items"] = [
    { key: "checks", label: `诊断结论 ${snapshot.checks.length}`, children: <ChecksTab {...props} /> },
    { key: "pipeline", label: "候选链路", children: <PipelineTab {...props} /> },
    { key: "evidence", label: "证据对比", children: <EvidenceTab {...props} /> },
    {
      key: "versions",
      label: "版本与事件",
      children: (
        <Space direction="vertical" size="middle" className="diagnostic-versions">
          <Descriptions bordered size="small" column={1} colon={false}>
            <Descriptions.Item label="快照版本">{snapshot.schema_version}</Descriptions.Item>
            <Descriptions.Item label="采集时间">{snapshot.captured_at}</Descriptions.Item>
            <Descriptions.Item label="正文持久化">{snapshot.content_capture_enabled ? "ENABLED" : "DISABLED"}</Descriptions.Item>
          </Descriptions>
          <Collapse items={[
            { key: "versions", label: "组件版本", children: json(snapshot.versions) },
            { key: "validation", label: "回答校验", children: json(snapshot.generation.validation) },
            { key: "ai", label: `AI Events (${aiEvents.length})`, children: json(aiEvents) },
          ]} />
        </Space>
      ),
    },
  ];
  return <Tabs items={items} />;
}
