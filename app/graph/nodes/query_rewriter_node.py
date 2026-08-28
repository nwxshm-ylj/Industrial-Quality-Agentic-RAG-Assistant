from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logger import log_business_event, observe_node
from app.graph.state import IndustrialRAGState
from app.observability.model_usage import invoke_observed_chat_model
from app.prompting import get_prompt_registry


llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    temperature=0.1,
    max_tokens=512,
)


@observe_node("query_rewriter")
def query_rewriter_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    retry_count = state.get("retry_count", 0)
    memory_text = _format_memory(state.get("memory_messages", []))
    feature_text = _format_query_features(state.get("query_features") or {})

    try:
        if retry_count == 0:
            prompt_component = "query_rewriter_initial"
            prompt_variables = {
                "memory_text": memory_text,
                "question": question,
                "intent": "rag",
                "query_features_text": feature_text,
            }
        else:
            prompt_component = "query_rewriter_retry"
            prompt_variables = {
                "memory_text": memory_text,
                "question": question,
                "intent": "rag",
                "query_features_text": feature_text,
                "missing_aspects_text": "、".join(
                    state.get("missing_aspects", [])
                )
                or "未明确识别",
            }

        rendered_prompt = get_prompt_registry().render(
            prompt_component,
            prompt_variables,
        )
        response = invoke_observed_chat_model(
            llm,
            list(rendered_prompt.messages),
            component="query_rewriter",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_reference=rendered_prompt.reference,
        )
        rewritten_query = str(response.content).strip() or question
    except Exception as exc:
        log_business_event(
            "query_rewriter_model_fallback",
            request_id=state.get("request_id"),
            session_id=state.get("session_id"),
            status="failed",
            error_message=type(exc).__name__,
            prompt_component=(
                "query_rewriter_initial" if retry_count == 0 else "query_rewriter_retry"
            ),
        )
        rewritten_query = question

    return {"rewritten_query": rewritten_query}


def _format_memory(memory_messages: list[dict]) -> str:
    if not memory_messages:
        return "无历史对话。"
    return "\n".join(
        f"{message.get('role', 'unknown')}: {message.get('content', '')}"
        for message in memory_messages
    )


def _format_query_features(features: dict) -> str:
    aspects = "、".join(features.get("requested_aspects", [])) or "未明确指定"
    doc_types = "、".join(features.get("preferred_doc_types", [])) or "不限定"
    anchors = "、".join(features.get("case_anchors", [])) or "未识别"
    entities = features.get("entities") or {}
    return "\n".join(
        [
            f"RAG内部任务模式：{features.get('task_mode', 'knowledge_lookup')}",
            f"需要问题追溯：{'是' if features.get('traceability_required') else '否'}",
            f"需要故障诊断：{'是' if features.get('diagnosis_required') else '否'}",
            f"用户要求的证据维度：{aspects}",
            f"优先文档类型（仅用于召回偏好，不是硬过滤）：{doc_types}",
            f"案例锚点：{anchors}",
            f"已识别实体：{entities}",
        ]
    )
