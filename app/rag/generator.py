from __future__ import annotations

import json
from typing import Any

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.observability.model_usage import invoke_observed_chat_model, stream_observed_chat_model
from app.prompting import get_prompt_registry
from app.streaming.events import emit_answer_token, has_stream_event_sink


class AnswerGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.1,
            max_tokens=1024,
        )

    def generate(
        self,
        question: str,
        contexts: list[dict],
        memory_messages: list[dict] | None = None,
        *,
        intent: str = "rag",
        evidence_enough: bool = True,
        evidence_confidence: float = 0.0,
        missing_aspects: list[str] | None = None,
    ) -> str:
        rendered_prompt = get_prompt_registry().render(
            "answer_generator",
            {
                "memory_text": self._format_memory(memory_messages),
                "question": question,
                "context_text": self._format_contexts(contexts),
                "intent": intent,
                "evidence_text": self._format_evidence_status(
                    evidence_enough=evidence_enough,
                    evidence_confidence=evidence_confidence,
                    missing_aspects=missing_aspects,
                ),
            },
        )

        if has_stream_event_sink():
            content_parts: list[str] = []
            for response_chunk in stream_observed_chat_model(
                self.llm,
                list(rendered_prompt.messages),
                component="answer_generator",
                provider=settings.llm_provider,
                model_name=settings.llm_model,
                prompt_reference=rendered_prompt.reference,
            ):
                delta = self._content_to_text(response_chunk.content)
                if delta:
                    content_parts.append(delta)
                    emit_answer_token(delta)
            content = "".join(content_parts)
        else:
            response = invoke_observed_chat_model(
                self.llm,
                list(rendered_prompt.messages),
                component="answer_generator",
                provider=settings.llm_provider,
                model_name=settings.llm_model,
                prompt_reference=rendered_prompt.reference,
            )
            content = self._content_to_text(response.content)

        if not content:
            return "模型已调用，但返回内容为空。请检查模型服务或稍后重试。"
        return str(content)

    def repair_answer(
        self,
        *,
        question: str,
        draft_answer: str,
        contexts: list[dict[str, Any]],
        validation: dict[str, Any],
        missing_aspects: list[str] | None = None,
    ) -> str:
        """Repair citation-contract violations once without adding new facts."""
        rendered_prompt = get_prompt_registry().render(
            "answer_repair",
            {
                "question": question,
                "draft_answer": draft_answer,
                "context_text": self._format_contexts(contexts),
                "validation_text": json.dumps(
                    validation,
                    ensure_ascii=False,
                    default=str,
                ),
                "missing_aspects": "、".join(missing_aspects or []) or "无",
            },
        )
        response = invoke_observed_chat_model(
            self.llm,
            list(rendered_prompt.messages),
            component="answer_repair",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_reference=rendered_prompt.reference,
        )
        content = self._content_to_text(response.content).strip()
        if not content:
            raise RuntimeError("回答修复模型返回空内容")
        return content

    @staticmethod
    def _content_to_text(content: object) -> str:
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content or "")

    @staticmethod
    def _format_memory(memory_messages: list[dict] | None) -> str:
        if not memory_messages:
            return "无历史对话。"
        role_names = {"user": "用户", "assistant": "助手"}
        return "\n".join(
            f"{role_names.get(message.get('role'), message.get('role', '未知'))}："
            f"{message.get('content', '')}"
            for message in memory_messages
        )

    @staticmethod
    def _format_evidence_status(
        *,
        evidence_enough: bool,
        evidence_confidence: float,
        missing_aspects: list[str] | None,
    ) -> str:
        missing = "、".join(missing_aspects or []) or "无"
        return (
            f"证据是否通过门禁：{'是' if evidence_enough else '否'}\n"
            f"证据可信度：{evidence_confidence:.3f}\n"
            f"缺失维度：{missing}"
        )

    @staticmethod
    def _format_contexts(contexts: list[dict[str, Any]]) -> str:
        if not contexts:
            return "未检索到相关资料。"
        formatted: list[str] = []
        for index, context in enumerate(contexts, start=1):
            label = context.get("citation_label") or f"资料{index}"
            heading_path = context.get("heading_path")
            if isinstance(heading_path, (list, tuple)):
                heading = " > ".join(str(value) for value in heading_path if value)
            else:
                heading = str(heading_path or "")
            page = context.get("page_number")
            if page is None:
                page_start = context.get("page_start")
                page_end = context.get("page_end")
                page = page_start if page_start == page_end else f"{page_start or ''}-{page_end or ''}"
            fields = [
                f"【{label}】",
                f"证据ID：{context.get('evidence_id') or f'E{index}'}",
                f"来源：{context.get('source') or '未知'}",
                f"文档类型：{context.get('doc_type') or '未知'}",
                f"文档ID：{context.get('doc_id') or '未知'}",
                f"chunk_id：{context.get('chunk_id') or '未知'}",
            ]
            if page not in (None, "", "-"):
                fields.append(f"页码：{page}")
            if heading:
                fields.append(f"章节：{heading}")
            if context.get("traceability_role"):
                fields.append(f"追溯角色：{context.get('traceability_role')}")
            if context.get("modality"):
                fields.append(f"模态：{context.get('modality')}")
            fields.extend(["内容：", str(context.get("text") or "")])
            formatted.append("\n".join(fields))
        return "\n\n".join(formatted)
