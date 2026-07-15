import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
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
import { ConversationTurn } from "../features/chat/ConversationTurn";
import { EvidencePanel } from "../features/chat/EvidencePanel";
import { shortenId } from "../features/chat/presentation";
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

interface AskVariables {
  turnId: string;
  request: ChatRequest;
}

export function ChatPage() {
  const { message, modal } = AntdApp.useApp();
  const [draft, setDraft] = useState("");
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const username = useAuthStore((state) => state.user?.username);
  const {
    sessionId,
    topK,
    turns,
    ensureOwner,
    setTopK,
    addPendingTurn,
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

  const askMutation = useMutation({
    mutationFn: ({ request }: AskVariables) => chatApi.ask(request),
    onSuccess: (response, variables) => {
      completeTurn(variables.turnId, response);
      setSelectedTurnId(variables.turnId);
    },
    onError: (error, variables) => {
      failTurn(variables.turnId, getApiErrorMessage(error));
      setSelectedTurnId(variables.turnId);
    },
  });

  const selectedResponse = useMemo(() => {
    const selectedTurn = turns.find((turn) => turn.id === selectedTurnId);
    return selectedTurn?.response || getLatestCompletedResponse(turns);
  }, [selectedTurnId, turns]);

  const handleSubmit = () => {
    const question = draft.trim();
    if (!question || askMutation.isPending) {
      return;
    }

    const turnId = addPendingTurn(question);
    setSelectedTurnId(turnId);
    setDraft("");
    askMutation.mutate({
      turnId,
      request: {
        question,
        top_k: topK,
        session_id: sessionId,
      },
    });
  };

  const handleNewConversation = () => {
    if (turns.length === 0) {
      startNewConversation();
      setSelectedTurnId(null);
      setDraft("");
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
          disabled={askMutation.isPending}
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
            disabled={askMutation.isPending}
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
              disabled={askMutation.isPending}
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
            <i className={askMutation.isPending ? "is-busy" : "is-online"} />
            {askMutation.isPending ? "WORKFLOW RUNNING" : "READY"}
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
              />
            ))
          )}
          <div ref={endRef} />
        </div>

        <ChatComposer
          value={draft}
          loading={askMutation.isPending}
          onChange={setDraft}
          onSubmit={handleSubmit}
        />
      </main>

      <EvidencePanel response={selectedResponse} />
    </div>
  );
}
