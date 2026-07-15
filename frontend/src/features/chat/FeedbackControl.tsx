import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { App as AntdApp, Button, Input, Tag } from "antd";

import { feedbackApi } from "../../api/feedback";
import { getApiErrorMessage } from "../../api/client";
import type { ChatResponse, FeedbackRating } from "../../api/types";
import { useChatStore } from "../../stores/chatStore";

interface FeedbackControlProps {
  turnId: string;
  question: string;
  response: ChatResponse;
}

const options: Array<{ rating: FeedbackRating; icon: string; label: string }> = [
  { rating: "positive", icon: "↑", label: "有用" },
  { rating: "neutral", icon: "–", label: "一般" },
  { rating: "negative", icon: "↓", label: "无用" },
];

export function FeedbackControl({ turnId, question, response }: FeedbackControlProps) {
  const { message } = AntdApp.useApp();
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [comment, setComment] = useState("");
  const requestKey = response.request_id || turnId;
  const submittedRating = useChatStore((state) => state.feedbackRatings[requestKey]);
  const markFeedback = useChatStore((state) => state.markFeedback);

  const mutation = useMutation({
    mutationFn: () => feedbackApi.submit({
      request_id: response.request_id,
      session_id: response.session_id,
      question,
      answer: response.answer,
      rating: rating as FeedbackRating,
      comment: comment.trim() || null,
      intent: response.intent,
      citations: response.citations,
      metadata: response.metadata,
    }),
    onSuccess: (result) => {
      markFeedback(requestKey, rating as FeedbackRating);
      message.success(result.message);
    },
    onError: (error) => {
      message.error(`反馈提交失败：${getApiErrorMessage(error)}`);
    },
  });

  if (submittedRating) {
    const selected = options.find((option) => option.rating === submittedRating);
    return (
      <div className="feedback-control feedback-control--submitted">
        <span>QUALITY FEEDBACK</span>
        <Tag bordered={false}>{selected?.icon} 已记录为“{selected?.label}”</Tag>
      </div>
    );
  }

  return (
    <div className="feedback-control">
      <div className="feedback-control__rating">
        <span>这次回答是否有帮助？</span>
        {options.map((option) => (
          <Button
            key={option.rating}
            size="small"
            type={rating === option.rating ? "primary" : "text"}
            disabled={mutation.isPending}
            onClick={() => setRating(option.rating)}
          >
            <b>{option.icon}</b>{option.label}
          </Button>
        ))}
      </div>
      {rating && (
        <div className="feedback-control__comment">
          <Input
            value={comment}
            maxLength={1000}
            disabled={mutation.isPending}
            placeholder="补充反馈备注（可选），例如：引用准确但排查顺序不够具体"
            onChange={(event) => setComment(event.target.value)}
          />
          <Button
            type="primary"
            size="small"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            提交反馈
          </Button>
        </div>
      )}
    </div>
  );
}
