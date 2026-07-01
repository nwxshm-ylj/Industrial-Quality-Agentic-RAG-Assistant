from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


FeedbackRating = Literal["positive", "negative", "neutral"]


class FeedbackCreateRequest(BaseModel):
    request_id: str | None = None
    session_id: str | None = None
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    rating: FeedbackRating
    comment: str | None = None
    intent: str | None = None
    citations: list[Any] | dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class FeedbackResponse(BaseModel):
    id: int
    status: str = "success"
    message: str = "反馈已记录"


class FeedbackItem(BaseModel):
    id: int
    request_id: str | None = None
    session_id: str | None = None
    username: str | None = None
    role: str | None = None
    question: str
    answer: str
    rating: FeedbackRating
    comment: str | None = None
    intent: str | None = None
    citations: list[Any] | dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class FeedbackStatsResponse(BaseModel):
    total: int
    positive_count: int
    negative_count: int
    neutral_count: int
    positive_rate: float
    negative_rate: float
    by_intent: dict[str, int]
