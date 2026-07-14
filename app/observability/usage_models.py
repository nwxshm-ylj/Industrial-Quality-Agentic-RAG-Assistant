from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AIUsageEvent:
    component: str
    operation: str
    provider: str
    model: str
    latency_ms: float
    event_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "success"
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    input_text_count: int | None = None
    input_char_count: int | None = None
    cost: float | None = None
    currency: str | None = None
    pricing_version: str | None = None
    measurement_source: str = "unavailable"
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class RetrievalUsageEvent:
    operation: str
    latency_ms: float
    top_k: int
    event_id: str = field(default_factory=lambda: str(uuid4()))
    vector_hit_count: int = 0
    keyword_hit_count: int = 0
    fused_hit_count: int = 0
    returned_count: int = 0
    reranker_used: bool = False
    retrieval_mode: str = "hybrid"
    degraded: bool = False
    degraded_reason: str | None = None
    qdrant_latency_ms: float | None = None
    opensearch_latency_ms: float | None = None
    fusion_latency_ms: float | None = None
    reranker_latency_ms: float | None = None
    collection_name: str | None = None
    keyword_index: str | None = None
    embedding_index_version: str | None = None
    status: str = "success"
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class RequestUsageContext:
    request_id: str
    trace_id: str | None = None
    session_id: str | None = None
    username: str | None = None
    role: str | None = None
    route: str | None = None
    method: str | None = None
    intent: str | None = None
    status: str = "started"
    http_status: int | None = None
    total_latency_ms: float | None = None
    evidence_score: float | None = None
    evidence_enough: bool | None = None
    retry_count: int = 0
    retrieval_mode: str | None = None
    degraded: bool = False
    degraded_reason: str | None = None
    context_count: int = 0
    citation_count: int = 0
    error_type: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    ai_events: list[AIUsageEvent] = field(default_factory=list)
    retrieval_events: list[RetrievalUsageEvent] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def input_tokens(self) -> int:
        return sum(event.input_tokens or 0 for event in self.ai_events)

    @property
    def output_tokens(self) -> int:
        return sum(event.output_tokens or 0 for event in self.ai_events)

    @property
    def total_tokens(self) -> int:
        return sum(event.total_tokens or 0 for event in self.ai_events)

    @property
    def embedding_tokens(self) -> int:
        return sum(
            event.total_tokens or event.input_tokens or 0
            for event in self.ai_events
            if event.operation.startswith("embedding_")
        )

    @property
    def estimated_cost(self) -> float:
        return round(sum(event.cost or 0.0 for event in self.ai_events), 8)
