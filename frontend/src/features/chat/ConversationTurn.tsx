import { Alert, Button, Progress, Skeleton, Tag, Typography } from "antd";
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
  const active = turn.status === "pending" || turn.status === "streaming";
  const currentStage = turn.currentStage;
  const visibleEvents = (turn.progressEvents || [])
    .filter((event) => event.status !== "running" || event === currentStage)
    .slice(-8);

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
          {active && (
            <div className="workflow-progress">
              <div className="workflow-progress__heading">
                <span className="agent-thinking__pulse" />
                <div>
                  <strong>{currentStage?.label || "正在启动 Agentic workflow"}</strong>
                  <small>
                    {currentStage
                      ? `${currentStage.node_name} · ${currentStage.status === "completed" ? "已完成" : "执行中"}`
                      : "正在建立流式连接并分配 request_id"}
                  </small>
                </div>
                <b>{turn.progress || 0}%</b>
              </div>
              <Progress
                percent={turn.progress || 0}
                showInfo={false}
                strokeColor="#0f766e"
                railColor="#e7ecef"
              />
              {visibleEvents.length > 0 && (
                <div className="workflow-progress__events">
                  {visibleEvents.map((event) => (
                    <span
                      key={`${event.sequence}-${event.node_name}-${event.status}`}
                      className={`is-${event.status}`}
                    >
                      <i />{event.label}
                      {event.status === "completed" && event.latency_ms != null
                        ? ` · ${event.latency_ms.toFixed(0)} ms`
                        : ""}
                    </span>
                  ))}
                </div>
              )}
              {turn.streamedAnswer ? (
                <div className="answer-markdown answer-markdown--streaming">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.streamedAnswer}</ReactMarkdown>
                  <span className="streaming-cursor" aria-hidden="true" />
                </div>
              ) : (
                <Skeleton active paragraph={{ rows: 3 }} title={false} />
              )}
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
