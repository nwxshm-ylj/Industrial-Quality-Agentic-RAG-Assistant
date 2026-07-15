import { Alert, Button, Skeleton, Tag, Typography } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatTurn } from "../../stores/chatStore";
import { FeedbackControl } from "./FeedbackControl";
import { formatLatency, getIntent, intentLabels, shortenId } from "./presentation";

interface ConversationTurnProps {
  turn: ChatTurn;
  selected: boolean;
  onInspect: () => void;
}

export function ConversationTurn({ turn, selected, onInspect }: ConversationTurnProps) {
  const response = turn.response;
  const intent = response ? getIntent(response) : "unknown";
  const latency = response?.metadata?.total_latency_ms;

  return (
    <article className={`conversation-turn${selected ? " conversation-turn--selected" : ""}`}>
      <div className="message-row message-row--user">
        <div className="message-avatar">你</div>
        <div className="message-bubble message-bubble--user">
          <Typography.Paragraph>{turn.question}</Typography.Paragraph>
        </div>
      </div>

      <div className="message-row message-row--assistant">
        <div className="message-avatar message-avatar--agent">AI</div>
        <div className="message-bubble message-bubble--assistant">
          {turn.status === "pending" && (
            <div className="agent-thinking">
              <span className="agent-thinking__pulse" />
              <div>
                <strong>Agentic workflow 正在执行</strong>
                <small>正在路由意图、检索证据并生成回答…</small>
              </div>
              <Skeleton active paragraph={{ rows: 3 }} title={false} />
            </div>
          )}

          {turn.status === "error" && (
            <Alert
              type="error"
              showIcon
              message="本轮请求失败"
              description={turn.errorMessage || "请检查 API 服务后重试。"}
            />
          )}

          {turn.status === "completed" && response && (
            <>
              <div className="answer-markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{response.answer || "暂无回答"}</ReactMarkdown>
              </div>
              <div className="answer-meta">
                <Tag bordered={false}>{intentLabels[intent] || intent}</Tag>
                <span>{formatLatency(latency)}</span>
                <span>{response.citations.length} 条引用</span>
                <span>RID {shortenId(response.request_id, 5)}</span>
                <Button type="link" size="small" onClick={onInspect}>
                  {selected ? "正在查看证据" : "查看证据与执行详情"}
                </Button>
              </div>
              <FeedbackControl
                turnId={turn.id}
                question={turn.question}
                response={response}
              />
            </>
          )}
        </div>
      </div>
    </article>
  );
}
