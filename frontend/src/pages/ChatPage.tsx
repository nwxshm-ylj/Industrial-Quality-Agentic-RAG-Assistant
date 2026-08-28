import { useEffect, useMemo, useRef, useState } from "react";
import {
  App as AntdApp,
  Button,
  Divider,
  Slider,
  Tag,
  Typography,
} from "antd";

import { chatApi } from "../api/chat";
import { getApiErrorMessage } from "../api/client";
import type { ChatRequest } from "../api/types";
import { ChatComposer } from "../features/chat/ChatComposer";
import type { ChatImageAttachment } from "../features/chat/imageAttachments";
import { ConversationTurn } from "../features/chat/ConversationTurn";
import { EvidencePanel } from "../features/chat/EvidencePanel";
import { shortenId } from "../features/chat/presentation";
import { AnswerDiagnosisDrawer } from "../features/diagnostics/AnswerDiagnosisDrawer";
import { useAuthStore } from "../stores/authStore";
import {
  getLatestCompletedResponse,
  useChatStore,
} from "../stores/chatStore";

const exampleQuestions = [
  {
    label: "故障诊断",
    question: "轮毂识别异常可能是什么原因？",
  },
  {
    label: "多轮追问",
    question: "那优先排查哪个？",
  },
  {
    label: "规则查询",
    question: "PR001 对应什么轮毂配置？",
  },
  {
    label: "数据分析",
    question: "最近一周 ZP8 工位误识别数量是多少？",
  },
  {
    label: "案例检索",
    question: "历史上有没有类似的轮毂误识别案例？",
  },
];

export function ChatPage() {
  const { message, modal } = AntdApp.useApp();
  const [draft, setDraft] = useState("");
  const [images, setImages] = useState<ChatImageAttachment[]>([]);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [diagnosisTurnId, setDiagnosisTurnId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const username = useAuthStore((state) => state.user?.username);
  const role = useAuthStore((state) => state.user?.role);
  const {
    sessionId,
    topK,
    retrievalMode,
    turns,
    ensureOwner,
    setTopK,
    setRetrievalMode,
    addPendingTurn,
    acceptStreamingTurn,
    updateTurnProgress,
    appendTurnToken,
    replaceTurnAnswer,
    completeTurn,
    failTurn,
    startNewConversation,
  } = useChatStore();

  useEffect(() => {
    if (username) {
      ensureOwner(username);
    }
  }, [ensureOwner, username]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const selectedResponse = useMemo(() => {
    const selectedTurn = turns.find((turn) => turn.id === selectedTurnId);
    return selectedTurn?.response || getLatestCompletedResponse(turns);
  }, [selectedTurnId, turns]);
  const diagnosisTurn = useMemo(
    () => turns.find((turn) => turn.id === diagnosisTurnId),
    [diagnosisTurnId, turns],
  );

  const handleSubmit = async () => {
    const question = draft.trim();
    if (!question || isStreaming) {
      return;
    }

    const submittedImages = images.map((image) => image.dataUrl);
    const turnId = addPendingTurn(
      question,
      images.map(({ id, name, dataUrl }) => ({ id, name, dataUrl })),
      retrievalMode,
    );
    setSelectedTurnId(turnId);
    setDraft("");
    setImages([]);
    setIsStreaming(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    let tokenBuffer = "";
    let tokenFlushTimer: ReturnType<typeof setTimeout> | null = null;
    const flushTokenBuffer = () => {
      if (tokenFlushTimer) {
        clearTimeout(tokenFlushTimer);
        tokenFlushTimer = null;
      }
      if (tokenBuffer) {
        appendTurnToken(turnId, tokenBuffer);
        tokenBuffer = "";
      }
    };

    try {
      const request: ChatRequest = {
        question,
        top_k: topK,
        session_id: sessionId,
        retrieval_mode: retrievalMode,
        ...(submittedImages.length > 0
          ? { multimodal_query: { images: submittedImages } }
          : {}),
      };
      const response = await chatApi.askStream(
        request,
        {
          onAccepted: (event) => acceptStreamingTurn(turnId, event),
          onProgress: (event) => updateTurnProgress(turnId, event),
          onToken: (event) => {
            tokenBuffer += event.delta;
            if (!tokenFlushTimer) {
              tokenFlushTimer = setTimeout(flushTokenBuffer, 40);
            }
          },
          onAnswerReplace: (event) => {
            flushTokenBuffer();
            replaceTurnAnswer(turnId, event.answer);
          },
        },
        controller.signal,
      );
      flushTokenBuffer();
      completeTurn(turnId, response);
      setSelectedTurnId(turnId);
    } catch (error) {
      flushTokenBuffer();
      const errorMessage = error instanceof DOMException && error.name === "AbortError"
        ? "已停止接收本轮流式响应"
        : getApiErrorMessage(error);
      failTurn(turnId, errorMessage);
      setSelectedTurnId(turnId);
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      setIsStreaming(false);
    }
  };

  const handleStopStreaming = () => {
    abortControllerRef.current?.abort();
  };

  const handleNewConversation = () => {
    if (turns.length === 0) {
      startNewConversation();
      setSelectedTurnId(null);
      setDraft("");
      setImages([]);
      return;
    }

    modal.confirm({
      title: "开始新会话？",
      content: "当前页面中的多轮记录将被清空，并生成新的 session_id。数据库中的历史消息不会被删除。",
      okText: "开始新会话",
      cancelText: "继续当前会话",
      onOk: () => {
        startNewConversation();
        setSelectedTurnId(null);
        setDraft("");
        setImages([]);
      },
    });
  };

  const copySessionId = async () => {
    try {
      await navigator.clipboard.writeText(sessionId);
      message.success("session_id 已复制");
    } catch {
      message.warning("浏览器未授权剪贴板访问");
    }
  };

  return (
    <div className="chat-page">
      <aside className="chat-sidebar">
        <Button
          block
          type="primary"
          disabled={isStreaming}
          onClick={handleNewConversation}
        >
          ＋ 新建会话
        </Button>

        <div className="session-card">
          <Typography.Text className="panel-kicker">ACTIVE SESSION</Typography.Text>
          <button type="button" onClick={copySessionId} title={sessionId}>
            <span>{shortenId(sessionId, 7)}</span>
            <b>复制</b>
          </button>
          <small>{turns.length} 轮本地对话 · 后端记忆按 session_id 加载</small>
        </div>

        <Divider />

        <div className="retrieval-control">
          <div>
            <Typography.Text className="panel-kicker">RETRIEVAL DEPTH</Typography.Text>
            <Tag bordered={false}>TOP K {topK}</Tag>
          </div>
          <Slider
            min={1}
            max={10}
            value={topK}
            disabled={isStreaming}
            onChange={setTopK}
          />
          <small>提高召回深度会增加证据覆盖，也可能提升响应延迟。</small>
        </div>

        <Divider />

        <div className="example-prompts">
          <Typography.Text className="panel-kicker">INDUSTRIAL PROMPTS</Typography.Text>
          {exampleQuestions.map((item) => (
            <button
              type="button"
              key={item.label}
              disabled={isStreaming}
              onClick={() => setDraft(item.question)}
            >
              <span>{item.label}</span>
              <p>{item.question}</p>
            </button>
          ))}
        </div>
      </aside>

      <main className="conversation-workspace">
        <div className="conversation-header">
          <div>
            <Typography.Text className="panel-kicker">AGENTIC RAG WORKSPACE</Typography.Text>
            <Typography.Title level={4}>工业质量智能问答</Typography.Title>
          </div>
          <div className="conversation-header__status">
            <i className={isStreaming ? "is-busy" : "is-online"} />
            {isStreaming ? "STREAMING" : "READY"}
            {isStreaming && (
              <Button type="link" size="small" onClick={handleStopStreaming}>
                停止接收
              </Button>
            )}
          </div>
        </div>

        <div className="conversation-scroll">
          {turns.length === 0 ? (
            <section className="conversation-empty">
              <div className="conversation-empty__mark"><span /><span /><span /></div>
              <Typography.Text className="panel-kicker">QUALITY KNOWLEDGE COPILOT</Typography.Text>
              <Typography.Title level={2}>从现场问题开始一轮可追溯对话</Typography.Title>
              <Typography.Paragraph>
                系统会根据意图选择知识检索、规则、SQL 或历史案例链路，并保留 request_id、引用与执行元数据。
              </Typography.Paragraph>
              <div className="empty-capabilities">
                <span>多轮记忆</span><span>混合检索</span><span>工具路由</span><span>证据追踪</span>
              </div>
            </section>
          ) : (
            turns.map((turn) => (
              <ConversationTurn
                key={turn.id}
                turn={turn}
                selected={selectedTurnId === turn.id}
                onInspect={() => setSelectedTurnId(turn.id)}
                onDiagnose={() => setDiagnosisTurnId(turn.id)}
              />
            ))
          )}
          <div ref={endRef} />
        </div>

        <ChatComposer
          value={draft}
          loading={isStreaming}
          images={images}
          retrievalMode={retrievalMode}
          onChange={setDraft}
          onImagesChange={setImages}
          onRetrievalModeChange={setRetrievalMode}
          onImageError={(errorMessage) => message.error(errorMessage)}
          onSubmit={handleSubmit}
        />
      </main>

      <EvidencePanel response={selectedResponse} />
      <AnswerDiagnosisDrawer
        open={Boolean(diagnosisTurnId)}
        question={diagnosisTurn?.question}
        response={diagnosisTurn?.response}
        progressEvents={diagnosisTurn?.progressEvents}
        canLoadHistorical={role === "admin" || role === "engineer"}
        onClose={() => setDiagnosisTurnId(null)}
      />
    </div>
  );
}
