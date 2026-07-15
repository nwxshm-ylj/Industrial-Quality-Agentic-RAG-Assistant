import { Button, Input, Tooltip } from "antd";
import type { KeyboardEvent } from "react";

interface ChatComposerProps {
  value: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function ChatComposer({
  value,
  loading,
  onChange,
  onSubmit,
}: ChatComposerProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!loading && value.trim()) {
        onSubmit();
      }
    }
  };

  return (
    <div className="chat-composer">
      <div className="chat-composer__input">
        <Input.TextArea
          aria-label="输入工业质量问题"
          autoSize={{ minRows: 2, maxRows: 6 }}
          disabled={loading}
          maxLength={4000}
          placeholder="描述质量问题、工位异常，或继续追问上一轮结论…"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="chat-composer__footer">
          <span>Enter 发送 · Shift + Enter 换行</span>
          <Tooltip title={!value.trim() ? "请输入问题" : "发送到 Agentic RAG"}>
            <Button
              type="primary"
              loading={loading}
              disabled={!value.trim()}
              onClick={onSubmit}
            >
              {loading ? "Agent 执行中" : "发送问题"}
            </Button>
          </Tooltip>
        </div>
      </div>
      <p>回答由企业知识库与工具链生成，请结合现场质量流程复核关键操作。</p>
    </div>
  );
}
