from __future__ import annotations

from app.core.logger import observe_node
from app.graph.query_features import (
    extract_query_features,
    is_general_chat,
    is_sql_query,
    normalize_intent_label,
)
from app.graph.state import IndustrialRAGState


@observe_node("intent_router")
def intent_router_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    intent = _deterministic_intent(question)
    return {
        "intent": intent,
        "query_features": extract_query_features(question, intent),
    }


def _deterministic_intent(question: str) -> str:
    """Route conservatively without invoking an external model."""
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
