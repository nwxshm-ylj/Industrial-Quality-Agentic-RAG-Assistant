from __future__ import annotations

import operator
from typing import Annotated, TypedDict, Literal, Any


IntentType = Literal[
    "rag",
    "sql",
    "general"
]


class IndustrialRAGState(TypedDict):
    question: str
    request_id: str
    session_id: str
    user: dict[str, Any] | None
    memory_enabled: bool
    memory_messages: list[dict]
    memory_metadata: dict[str, Any]
    knowledge_graph_metadata: dict[str, Any]
    retrieval_filters: dict[str, list[str]] | None
    multimodal_query: dict[str, Any] | None
    intent: IntentType
    query_features: dict[str, Any]
    rewritten_query: str
    contexts: list[dict]
    generation_contexts: list[dict]
    generation_context_metadata: dict[str, Any]
    answer: str
    citations: list[dict]
    retrieval_metadata: dict[str, Any]
    evidence_score: float
    evidence_enough: bool
    evidence_confidence: float
    evidence_reasons: list[str]
    missing_aspects: list[str]
    abstain_reason: str | None
    answer_abstained: bool
    draft_answer: str
    generation_retry_count: int
    generation_repair_error: str | None
    answer_validation: dict[str, Any]
    answer_validation_history: Annotated[list[dict[str, Any]], operator.add]
    answer_structure: dict[str, Any]
    generation_quality_passed: bool
    citation_pruned: bool
    retry_count: int
    top_k: int
    rule_result: dict[str, Any] | None
    sql_result: dict[str, Any] | None
    case_result: dict[str, Any] | None
