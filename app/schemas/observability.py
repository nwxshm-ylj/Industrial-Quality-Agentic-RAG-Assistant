from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UsageOverviewResponse(BaseModel):
    total_requests: int
    success_count: int
    failed_count: int
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    embedding_tokens: int
    calculated_cost: float
    currency: str | None = None
    degraded_count: int
    degraded_rate: float
    evidence_enough_count: int


class UsageTimeseriesItem(BaseModel):
    bucket: datetime
    request_count: int
    failed_count: int
    avg_latency_ms: float
    total_tokens: int
    calculated_cost: float
    degraded_count: int


class ModelUsageItem(BaseModel):
    provider: str
    model: str
    operation: str
    call_count: int
    failed_count: int
    avg_latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    calculated_cost: float
    currency: str | None = None


class IntentUsageItem(BaseModel):
    intent: str
    request_count: int
    failed_count: int
    avg_latency_ms: float
    total_tokens: int
    calculated_cost: float


class RetrievalUsageItem(BaseModel):
    retrieval_mode: str
    request_count: int
    degraded_count: int
    failed_count: int
    avg_latency_ms: float
    avg_qdrant_latency_ms: float
    avg_opensearch_latency_ms: float
    avg_returned_count: float


class UsageTimeseriesResponse(BaseModel):
    items: list[UsageTimeseriesItem] = Field(default_factory=list)


class ModelUsageResponse(BaseModel):
    items: list[ModelUsageItem] = Field(default_factory=list)


class IntentUsageResponse(BaseModel):
    items: list[IntentUsageItem] = Field(default_factory=list)


class RetrievalUsageResponse(BaseModel):
    items: list[RetrievalUsageItem] = Field(default_factory=list)


class RequestUsageDetailsResponse(BaseModel):
    request: dict[str, Any]
    ai_events: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_events: list[dict[str, Any]] = Field(default_factory=list)


class DiagnosticCheck(BaseModel):
    code: str
    status: str
    title: str
    detail: str
    stage: str


class RequestDiagnosticsResponse(BaseModel):
    request_id: str | None = None
    snapshot_available: bool
    snapshot: dict[str, Any] | None = None
    checks: list[DiagnosticCheck] = Field(default_factory=list)
    request: dict[str, Any]
    ai_events: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_events: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
