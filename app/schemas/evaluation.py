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
