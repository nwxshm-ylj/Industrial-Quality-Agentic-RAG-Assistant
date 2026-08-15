import { Button, Input, Tooltip } from "antd";
import { useRef } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";

import {
  appendImageAttachments,
  MAX_CHAT_IMAGES,
  type ChatImageAttachment,
} from "./imageAttachments";

interface ChatComposerProps {
  value: string;
  loading: boolean;
  images: ChatImageAttachment[];
  onChange: (value: string) => void;
  onImagesChange: (images: ChatImageAttachment[]) => void;
  onImageError: (message: string) => void;
  onSubmit: () => void;
}

export function ChatComposer({
  value,
  loading,
  images,
  onChange,
  onImagesChange,
  onImageError,
  onSubmit,
}: ChatComposerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!loading && value.trim()) {
        onSubmit();
      }
    }
  };

  const handleImageSelect = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    try {
      onImagesChange(await appendImageAttachments(images, files));
    } catch (error) {
      onImageError(error instanceof Error ? error.message : "图片读取失败");
    }
  };

  const removeImage = (id: string) => {
    onImagesChange(images.filter((image) => image.id !== id));
  };

  return (
    <div className="chat-composer">
      <div className="chat-composer__input">
        {images.length > 0 && (
          <div className="chat-composer__images" aria-label="已选择图片">
            {images.map((image) => (
              <div className="chat-composer__image" key={image.id}>
                <img src={image.dataUrl} alt={image.name} />
                <button
                  type="button"
                  aria-label={`移除图片 ${image.name}`}
                  disabled={loading}
                  onClick={() => removeImage(image.id)}
                >
                  ×
                </button>
                <span title={image.name}>{image.name}</span>
              </div>
            ))}
          </div>
        )}
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
          <div className="chat-composer__actions">
            <input
              ref={fileInputRef}
              className="chat-composer__file-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              disabled={loading || images.length >= MAX_CHAT_IMAGES}
              onChange={handleImageSelect}
            />
            <Button
              type="text"
              disabled={loading || images.length >= MAX_CHAT_IMAGES}
              onClick={() => fileInputRef.current?.click()}
            >
              添加图片 {images.length > 0 ? `${images.length}/${MAX_CHAT_IMAGES}` : ""}
            </Button>
            <span>Enter 发送 · Shift + Enter 换行</span>
          </div>
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
