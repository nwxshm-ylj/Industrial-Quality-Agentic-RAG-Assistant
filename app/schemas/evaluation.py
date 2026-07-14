from datetime import datetime

from pydantic import BaseModel, Field


class EvalItemInfo(BaseModel):
    id: int
    run_id: str
    question_id: str | None = None
    question: str
    expected_intent: str | None = None
    actual_intent: str | None = None
    expected_keywords: list[str] = Field(default_factory=list)
    keyword_hit: bool | None = None
    expected_sources: list[str] = Field(default_factory=list)
    source_hit: bool | None = None
    answer: str | None = None
    latency_ms: float | None = None
    passed: bool | None = None
    created_at: datetime


class EvalRunInfo(BaseModel):
    run_id: str
    username: str | None = None
    status: str
    total_questions: int
    intent_accuracy: float | None = None
    source_hit_rate: float | None = None
    answer_keyword_hit_rate: float | None = None
    memory_followup_success_rate: float | None = None
    avg_latency_ms: float | None = None
    report_path: str | None = None
    created_at: datetime


class EvalRunResponse(EvalRunInfo):
    items: list[EvalItemInfo] = Field(default_factory=list)


class EvalRunListResponse(BaseModel):
    runs: list[EvalRunInfo]
    total: int


class RetrievalEvalRunRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=100)
    k_values: list[int] = Field(
        default_factory=lambda: [1, 3, 5],
        min_length=1,
        max_length=10,
    )
    max_questions: int | None = Field(default=None, ge=1, le=1000)


class RetrievalEvalRunSummary(BaseModel):
    total_questions: int
    successful_questions: int
    failed_questions: int
    degraded_questions: int
    degraded_rate: float


class RetrievalEvalRunInfo(BaseModel):
    run_id: str
    status: str
    dataset_name: str | None = None
    started_at: datetime
    completed_at: datetime
    username: str | None = None
    config: dict
    summary: RetrievalEvalRunSummary
    metrics: dict[str, float]
    latency: dict
    report_path: str | None = None


class RetrievalEvalRunResponse(RetrievalEvalRunInfo):
    items: list[dict] = Field(default_factory=list)


class RetrievalEvalRunListResponse(BaseModel):
    runs: list[RetrievalEvalRunInfo] = Field(default_factory=list)
    total: int
