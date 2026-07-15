import {
  Alert,
  Collapse,
  Descriptions,
  Empty,
  Progress,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  type CollapseProps,
  type TabsProps,
} from "antd";

import type { ChatResponse, Citation, MemoryMessage } from "../../api/types";
import {
  formatLatency,
  formatScore,
  getCitationScore,
  getIntent,
  intentLabels,
  shortenId,
} from "./presentation";

interface EvidencePanelProps {
  response: ChatResponse | null;
}

function jsonBlock(value: unknown) {
  return <pre className="json-viewer">{JSON.stringify(value, null, 2)}</pre>;
}

function citationLabel(citation: Citation, index: number): string {
  return citation.source || citation.doc_id || citation.chunk_id || `引用 ${index + 1}`;
}

function OverviewTab({ response }: { response: ChatResponse }) {
  const metadata = response.metadata || {};
  const intent = getIntent(response);
  const evidenceScore = response.evidence_score ?? metadata.evidence_score;
  const evidenceEnough = response.evidence_enough ?? metadata.evidence_enough;
  const usage = metadata.usage;

  return (
    <div className="evidence-overview">
      {metadata.degraded === true && (
        <Alert
          type="warning"
          showIcon
          message="检索已降级"
          description={String(metadata.degraded_reason || "关键词检索不可用，当前使用向量检索结果。")}
        />
      )}

      <div className="evidence-score-card">
        <div>
          <span>证据充分度</span>
          <strong>{evidenceEnough === true ? "ENOUGH" : evidenceEnough === false ? "CHECK" : "--"}</strong>
        </div>
        <Progress
          percent={Math.max(0, Math.min(100, Number(evidenceScore || 0) * 100))}
          showInfo={false}
          strokeColor="#0f766e"
          trailColor="#e7ecef"
        />
        <small>Evidence score {formatScore(evidenceScore)}</small>
      </div>

      <Descriptions column={1} size="small" colon={false} className="runtime-descriptions">
        <Descriptions.Item label="意图">
          <Tag bordered={false}>{intentLabels[intent] || intent}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="总延迟">{formatLatency(metadata.total_latency_ms)}</Descriptions.Item>
        <Descriptions.Item label="检索模式">{String(metadata.retrieval_mode || "--")}</Descriptions.Item>
        <Descriptions.Item label="重试次数">{String(response.retry_count ?? metadata.retry_count ?? 0)}</Descriptions.Item>
        <Descriptions.Item label="引用数量">{response.citations.length}</Descriptions.Item>
        <Descriptions.Item label="历史消息">{response.memory_messages?.length || 0}</Descriptions.Item>
      </Descriptions>

      <div className="identifier-list">
        <Tooltip title={response.request_id || ""}>
          <span><b>REQUEST</b>{shortenId(response.request_id)}</span>
        </Tooltip>
        <Tooltip title={response.session_id || ""}>
          <span><b>SESSION</b>{shortenId(response.session_id)}</span>
        </Tooltip>
        {metadata.trace_id && (
          <Tooltip title={String(metadata.trace_id)}>
            <span><b>TRACE</b>{shortenId(String(metadata.trace_id))}</span>
          </Tooltip>
        )}
      </div>

      {usage && (
        <div className="usage-summary">
          <Typography.Text className="panel-kicker">MODEL USAGE</Typography.Text>
          <div>
            <span><strong>{String(usage.total_tokens ?? 0)}</strong>tokens</span>
            <span><strong>{String(usage.llm_call_count ?? 0)}</strong>LLM calls</span>
            <span><strong>{String(usage.embedding_tokens ?? 0)}</strong>embedding</span>
          </div>
        </div>
      )}

      {response.rewritten_query && (
        <div className="rewritten-query">
          <Typography.Text className="panel-kicker">REWRITTEN QUERY</Typography.Text>
          <p>{response.rewritten_query}</p>
        </div>
      )}
    </div>
  );
}

function CitationsTab({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="本轮未返回引用" />;
  }

  return (
    <div className="citation-list">
      {citations.map((citation, index) => (
        <article className="citation-card" key={citation.chunk_id || `${citationLabel(citation, index)}-${index}`}>
          <header>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{citationLabel(citation, index)}</strong>
              <small>{citation.doc_type || "未分类"} · {citation.version || "--"}</small>
            </div>
            <b>{formatScore(getCitationScore(citation))}</b>
          </header>
          <dl>
            <div><dt>chunk</dt><dd>{citation.chunk_id || "--"}</dd></div>
            <div><dt>retrieval</dt><dd>{citation.retrieval_source || citation.final_score_type || "--"}</dd></div>
          </dl>
        </article>
      ))}
    </div>
  );
}

function DetailsTab({ response }: { response: ChatResponse }) {
  const memory = (response.memory_messages || []) as MemoryMessage[];
  const collapseItems: CollapseProps["items"] = [
    response.rule_result && { key: "rule", label: "Rule Tool", children: jsonBlock(response.rule_result) },
    response.sql_result && { key: "sql", label: "SQL Tool", children: jsonBlock(response.sql_result) },
    response.case_result && { key: "case", label: "Case Retriever", children: jsonBlock(response.case_result) },
    response.contexts?.length && { key: "contexts", label: `检索上下文 (${response.contexts.length})`, children: jsonBlock(response.contexts) },
    response.metadata?.prompt_versions && { key: "prompts", label: "Prompt 版本", children: jsonBlock({
      release: response.metadata.prompt_release,
      versions: response.metadata.prompt_versions,
    }) },
    { key: "raw", label: "兼容响应 JSON", children: jsonBlock(response) },
  ].filter(Boolean) as CollapseProps["items"];

  return (
    <div className="execution-details">
      {memory.length > 0 && (
        <div className="memory-preview">
          <Typography.Text className="panel-kicker">LOADED MEMORY</Typography.Text>
          {memory.map((message, index) => (
            <div key={`${message.role || "message"}-${index}`}>
              <b>{message.role === "assistant" ? "AI" : "USER"}</b>
              <p>{message.content || ""}</p>
            </div>
          ))}
        </div>
      )}
      <Collapse ghost size="small" items={collapseItems} />
    </div>
  );
}

export function EvidencePanel({ response }: EvidencePanelProps) {
  if (!response) {
    return (
      <aside className="evidence-panel evidence-panel--empty">
        <div className="evidence-panel__heading">
          <Typography.Text className="panel-kicker">EVIDENCE & RUNTIME</Typography.Text>
          <Typography.Title level={4}>证据与执行详情</Typography.Title>
        </div>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="发送问题后查看本轮检索证据" />
      </aside>
    );
  }

  const items: TabsProps["items"] = [
    { key: "overview", label: "运行摘要", children: <OverviewTab response={response} /> },
    { key: "citations", label: `引用 ${response.citations.length}`, children: <CitationsTab citations={response.citations} /> },
    { key: "details", label: "执行详情", children: <DetailsTab response={response} /> },
  ];

  return (
    <aside className="evidence-panel">
      <div className="evidence-panel__heading">
        <Typography.Text className="panel-kicker">EVIDENCE & RUNTIME</Typography.Text>
        <Typography.Title level={4}>证据与执行详情</Typography.Title>
      </div>
      <Tabs items={items} size="small" />
    </aside>
  );
}
