from __future__ import annotations

from time import perf_counter
from typing import Any

from app.core.metrics import record_model_usage
from app.core.telemetry import traced_span
from app.core.telemetry_context import add_ai_usage_event
from app.observability.pricing import get_model_price_catalog
from app.observability.usage_models import AIUsageEvent


def invoke_observed_chat_model(
    model: Any,
    messages: list[Any],
    *,
    component: str,
    provider: str,
    model_name: str,
) -> Any:
    operation = "chat_completion"
    started_at = perf_counter()
    attributes = {
        "ai.provider": provider,
        "ai.model": model_name,
        "ai.operation": operation,
        "rag.component": component,
    }
    try:
        with traced_span(f"ai.{component}", attributes=attributes):
            response = model.invoke(messages)
    except Exception as exc:
        latency_ms = (perf_counter() - started_at) * 1000
        _record_ai_event(
            component=component,
            operation=operation,
            provider=provider,
            model_name=model_name,
            latency_ms=latency_ms,
            status="failed",
            error_type=type(exc).__name__,
        )
        raise

    latency_ms = (perf_counter() - started_at) * 1000
    usage = extract_chat_usage(response)
    _record_ai_event(
        component=component,
        operation=operation,
        provider=provider,
        model_name=model_name,
        latency_ms=latency_ms,
        status="success",
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        total_tokens=usage["total_tokens"],
        measurement_source=usage["measurement_source"],
    )
    return response


def record_embedding_call(
    *,
    component: str,
    operation: str,
    provider: str,
    model_name: str,
    latency_ms: float,
    input_text_count: int,
    input_char_count: int,
    input_tokens: int | None,
    status: str,
    error_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _record_ai_event(
        component=component,
        operation=operation,
        provider=provider,
        model_name=model_name,
        latency_ms=latency_ms,
        status=status,
        input_tokens=input_tokens,
        output_tokens=None,
        total_tokens=input_tokens,
        input_text_count=input_text_count,
        input_char_count=input_char_count,
        measurement_source="provider" if input_tokens is not None else "unavailable",
        error_type=error_type,
        metadata=metadata,
    )


def extract_chat_usage(response: Any) -> dict[str, int | str | None]:
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage", {}) or {}

    input_tokens = _as_optional_int(
        usage_metadata.get("input_tokens", token_usage.get("prompt_tokens"))
    )
    output_tokens = _as_optional_int(
        usage_metadata.get("output_tokens", token_usage.get("completion_tokens"))
    )
    total_tokens = _as_optional_int(
        usage_metadata.get("total_tokens", token_usage.get("total_tokens"))
    )
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "measurement_source": (
            "provider"
            if any(value is not None for value in (input_tokens, output_tokens, total_tokens))
            else "unavailable"
        ),
    }


def _record_ai_event(
    *,
    component: str,
    operation: str,
    provider: str,
    model_name: str,
    latency_ms: float,
    status: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    input_text_count: int | None = None,
    input_char_count: int | None = None,
    measurement_source: str = "unavailable",
    error_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    calculated_cost = get_model_price_catalog().calculate(
        provider=provider,
        model=model_name,
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    event = AIUsageEvent(
        component=component,
        operation=operation,
        provider=provider,
        model=model_name,
        latency_ms=round(latency_ms, 2),
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_text_count=input_text_count,
        input_char_count=input_char_count,
        cost=calculated_cost.amount if calculated_cost else None,
        currency=calculated_cost.currency if calculated_cost else None,
        pricing_version=(
            calculated_cost.pricing_version if calculated_cost else None
        ),
        measurement_source=measurement_source,
        error_type=error_type,
        metadata=metadata or {},
    )
    add_ai_usage_event(event)
    record_model_usage(
        provider=provider,
        model=model_name,
        operation=operation,
        status=status,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        measurement_source=measurement_source,
        cost=event.cost,
        currency=event.currency,
    )


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

