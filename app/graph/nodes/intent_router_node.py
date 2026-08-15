from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logger import log_business_event, observe_node
from app.graph.query_features import (
    extract_query_features,
    has_industrial_signal,
    is_general_chat,
    is_sql_query,
    normalize_intent_label,
)
from app.graph.state import IndustrialRAGState
from app.observability.model_usage import invoke_observed_chat_model
from app.prompting import get_prompt_registry


llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    temperature=0,
    max_tokens=128,
)

VALID_INTENTS = {"rag", "sql", "general"}


@observe_node("intent_router")
def intent_router_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    memory_text = _format_memory(state.get("memory_messages", []))

    try:
        rendered_prompt = get_prompt_registry().render(
            "intent_router",
            {"memory_text": memory_text, "question": question},
        )
        response = invoke_observed_chat_model(
            llm,
            list(rendered_prompt.messages),
            component="intent_router",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_reference=rendered_prompt.reference,
        )
        intent = _parse_model_intent(response.content)
    except Exception as exc:
        log_business_event(
            "intent_router_model_fallback",
            request_id=state.get("request_id"),
            session_id=state.get("session_id"),
            status="failed",
            error_message=type(exc).__name__,
            prompt_component="intent_router",
        )
        intent = _rule_based_intent(question)

    # SQL is a privileged and high-impact branch. Model output alone cannot
    # activate it; the query must also match the known structured-data domain.
    if is_sql_query(question):
        intent = "sql"
    elif intent == "sql":
        intent = "rag"

    if is_general_chat(question):
        intent = "general"
    elif intent == "general" and has_industrial_signal(question):
        intent = "rag"

    intent = normalize_intent_label(intent)
    return {
        "intent": intent,
        "query_features": extract_query_features(question, intent),
    }


def _parse_model_intent(content: object) -> str:
    text = str(content or "").strip().lower()
    for intent in ("general", "sql", "rag"):
        if intent in text:
            return intent
    return "rag"


def _format_memory(memory_messages: list[dict]) -> str:
    if not memory_messages:
        return "无历史对话。"
    return "\n".join(
        f"{message.get('role', 'unknown')}: {message.get('content', '')}"
        for message in memory_messages
    )


def _rule_based_intent(question: str) -> str:
    if is_sql_query(question):
        return "sql"
    if is_general_chat(question):
        return "general"
    return "rag"


def route_after_intent(state: IndustrialRAGState) -> str:
    intent = normalize_intent_label(state.get("intent", "rag"))
    if intent == "general":
        return "generate"
    if intent == "sql":
        return "sql"
    return "rag"
