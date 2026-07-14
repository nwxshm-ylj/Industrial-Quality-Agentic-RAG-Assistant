from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from time import perf_counter
from typing import Any, TypeVar, cast

from app.core.metrics import record_node_execution
from app.core.sensitive_filter import sanitize_telemetry_value
from app.core.telemetry import get_current_trace_ids, traced_span
from app.core.telemetry_context import get_request_context


SERVICE_NAME = os.getenv(
    "OTEL_SERVICE_NAME",
    "industrial-quality-rag-api",
)
SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = get_current_trace_ids()
        request_context = get_request_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service_name": SERVICE_NAME,
            "service_version": SERVICE_VERSION,
            "environment": ENVIRONMENT,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        if request_context is not None:
            payload.update(
                {
                    "request_id": request_context.request_id,
                    "session_id": request_context.session_id,
                }
            )
        payload.update(
            sanitize_telemetry_value(getattr(record, "event_data", {}))
        )

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            sanitize_telemetry_value(payload),
            ensure_ascii=False,
            default=str,
        )


logger = logging.getLogger("industrial_rag")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logger.setLevel(log_level)
logger.propagate = False


def log_node_event(
    state: dict[str, Any],
    node_name: str,
    latency_ms: float,
    status: str,
    intent: str | None = None,
    error: str | None = None,
    exc_info: bool = False,
) -> None:
    resolved_intent = intent if intent is not None else state.get("intent")
    record_node_execution(
        node_name=node_name,
        intent=resolved_intent,
        status=status,
        latency_ms=latency_ms,
    )
    event_data = {
        "request_id": state.get("request_id", "unknown"),
        "session_id": state.get("session_id", "default"),
        "node_name": node_name,
        "intent": resolved_intent,
        "latency_ms": round(latency_ms, 2),
        "status": status,
    }
    if error:
        event_data["error"] = error

    level = logging.ERROR if status == "error" else logging.INFO
    logger.log(
        level,
        "node_execution",
        extra={"event_data": event_data},
        exc_info=exc_info,
    )


def log_security_event(
    *,
    request_id: str | None,
    username: str | None,
    role: str | None,
    action: str,
    status: str,
    error_message: str | None = None,
) -> None:
    level = (
        logging.WARNING
        if status in {"failed", "denied", "invalid"}
        else logging.INFO
    )
    logger.log(
        level,
        action,
        extra={
            "event_data": {
                "request_id": request_id,
                "username": username,
                "role": role,
                "action": action,
                "status": status,
                "error_message": error_message,
            }
        },
    )


def log_business_event(
    action: str,
    *,
    request_id: str | None = None,
    session_id: str | None = None,
    username: str | None = None,
    role: str | None = None,
    status: str = "success",
    latency_ms: float | None = None,
    error_message: str | None = None,
    **fields: Any,
) -> None:
    event_data: dict[str, Any] = {
        "request_id": request_id,
        "session_id": session_id,
        "username": username,
        "role": role,
        "action": action,
        "status": status,
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        "error_message": error_message,
    }
    event_data.update(fields)
    level = logging.ERROR if status == "failed" else logging.INFO
    logger.log(level, action, extra={"event_data": event_data})


NodeFunction = TypeVar("NodeFunction", bound=Callable[..., dict])


def observe_node(node_name: str) -> Callable[[NodeFunction], NodeFunction]:
    def decorator(func: NodeFunction) -> NodeFunction:
        @wraps(func)
        def wrapper(state: dict[str, Any], *args: Any, **kwargs: Any) -> dict:
            started_at = perf_counter()
            span_attributes = {
                "rag.node.name": node_name,
                "rag.intent": state.get("intent"),
                "rag.retry_count": state.get("retry_count", 0),
            }
            with traced_span(
                f"langgraph.{node_name}",
                attributes=span_attributes,
            ) as span:
                try:
                    result = func(state, *args, **kwargs)
                except Exception as exc:
                    log_node_event(
                        state=state,
                        node_name=node_name,
                        latency_ms=(perf_counter() - started_at) * 1000,
                        status="error",
                        error=str(exc),
                        exc_info=True,
                    )
                    raise

                result_intent = (
                    result.get("intent")
                    if isinstance(result, dict)
                    else None
                )
                resolved_intent = result_intent or state.get("intent")
                span.set_attribute("rag.intent", str(resolved_intent or "unknown"))
                if isinstance(result, dict):
                    contexts = result.get("contexts")
                    if isinstance(contexts, list):
                        span.set_attribute("rag.context_count", len(contexts))
                    retrieval_metadata = result.get("retrieval_metadata")
                    if isinstance(retrieval_metadata, dict):
                        span.set_attribute(
                            "rag.retrieval.degraded",
                            bool(retrieval_metadata.get("degraded", False)),
                        )
                        span.set_attribute(
                            "rag.retrieval.mode",
                            str(
                                retrieval_metadata.get(
                                    "retrieval_mode",
                                    "unknown",
                                )
                            ),
                        )
                    if result.get("evidence_enough") is not None:
                        span.set_attribute(
                            "rag.evidence_enough",
                            bool(result["evidence_enough"]),
                        )
                log_node_event(
                    state=state,
                    node_name=node_name,
                    latency_ms=(perf_counter() - started_at) * 1000,
                    status="success",
                    intent=result_intent,
                )
                return result

        return cast(NodeFunction, wrapper)

    return decorator
