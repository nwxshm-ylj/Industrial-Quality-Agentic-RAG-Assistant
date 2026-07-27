from typing import TypedDict, Literal, Any


IntentType = Literal[
    "doc_qa",
    "fault_diagnosis",
    "case_search",
    "rule_query",
    "sql_analysis",
    "general"
]


class IndustrialRAGState(TypedDict):
    question: str
    request_id: str
    session_id: str
    user: dict[str, Any] | None
    memory_messages: list[dict]
    memory_metadata: dict[str, Any]
    knowledge_graph_metadata: dict[str, Any]
    retrieval_filters: dict[str, list[str]] | None
    multimodal_query: dict[str, Any] | None
    intent: IntentType
    rewritten_query: str
    contexts: list[dict]
    answer: str
    citations: list[dict]
    retrieval_metadata: dict[str, Any]
    evidence_score: float
    evidence_enough: bool
    retry_count: int
    top_k: int
    rule_result: dict[str, Any] | None
    sql_result: dict[str, Any] | None
    case_result: dict[str, Any] | None
