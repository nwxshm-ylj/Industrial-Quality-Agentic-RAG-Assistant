from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    top_k: int = Field(default=5, ge=1, le=10)
    session_id: str = Field(default="default", description="会话ID")


class Citation(BaseModel):
    source: str | None = None
    doc_type: str | None = None
    chunk_id: str | None = None
    score: float | None = None
    retrieval_source: str | None = None
    vector_score: float | None = None
    bm25_score: float | None = None
    hybrid_score: float | None = None
    rerank_score: float | None = None
    final_score_type: str | None = None


class ChatResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]

    request_id: str | None = None
    session_id: str | None = None
    memory_messages: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None

    intent: str | None = None
    rewritten_query: str | None = None
    evidence_score: float | None = None
    evidence_enough: bool | None = None
    retry_count: int | None = None

    rule_result: dict[str, Any] | None = None
    sql_result: dict[str, Any] | None = None
    case_result: dict[str, Any] | None = None
    contexts: list[dict[str, Any]] | None = None