from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

from app.observability.usage_models import (
    AIUsageEvent,
    RequestUsageContext,
    RetrievalUsageEvent,
)


_current_usage_context: ContextVar[RequestUsageContext | None] = ContextVar(
    "industrial_rag_usage_context",
    default=None,
)


def start_request_context(
    request_id: str,
    *,
    route: str | None = None,
    method: str | None = None,
) -> Token:
    context = RequestUsageContext(
        request_id=request_id,
        route=route,
        method=method,
    )
    return _current_usage_context.set(context)


def reset_request_context(token: Token) -> None:
    _current_usage_context.reset(token)


def get_request_context() -> RequestUsageContext | None:
    return _current_usage_context.get()


def update_request_context(**fields: Any) -> RequestUsageContext | None:
    context = get_request_context()
    if context is None:
        return None

    for key, value in fields.items():
        if hasattr(context, key):
            setattr(context, key, value)
        else:
            context.attributes[key] = value
    return context


def complete_request_context(
    *,
    status: str,
    http_status: int | None = None,
    total_latency_ms: float | None = None,
    error_type: str | None = None,
) -> RequestUsageContext | None:
    context = update_request_context(
        status=status,
        http_status=http_status,
        total_latency_ms=total_latency_ms,
        error_type=error_type,
    )
    if context is not None:
        context.completed_at = datetime.now(timezone.utc)
    return context


def add_ai_usage_event(event: AIUsageEvent) -> None:
    context = get_request_context()
    if context is not None:
        context.ai_events.append(event)


def add_retrieval_usage_event(event: RetrievalUsageEvent) -> None:
    context = get_request_context()
    if context is not None:
        context.retrieval_events.append(event)

