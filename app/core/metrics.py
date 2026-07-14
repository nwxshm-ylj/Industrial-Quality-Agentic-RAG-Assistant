from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Iterator


try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
except ImportError:  # pragma: no cover - dependencies are installed in Docker
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    Counter = Gauge = Histogram = None  # type: ignore[assignment]
    generate_latest = None


_LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
)
_METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _counter(name: str, description: str, labels: tuple[str, ...]):
    return Counter(name, description, labels) if Counter and _METRICS_ENABLED else None


def _gauge(name: str, description: str, labels: tuple[str, ...]):
    return Gauge(name, description, labels) if Gauge and _METRICS_ENABLED else None


def _histogram(name: str, description: str, labels: tuple[str, ...]):
    return (
        Histogram(name, description, labels, buckets=_LATENCY_BUCKETS)
        if Histogram and _METRICS_ENABLED
        else None
    )


HTTP_REQUESTS = _counter(
    "industrial_rag_http_requests_total",
    "HTTP requests processed by the API",
    ("method", "route", "status_class"),
)
HTTP_DURATION = _histogram(
    "industrial_rag_http_request_duration_seconds",
    "HTTP request duration",
    ("method", "route"),
)
HTTP_IN_PROGRESS = _gauge(
    "industrial_rag_http_requests_in_progress",
    "HTTP requests currently being processed",
    ("method", "route"),
)
GRAPH_REQUESTS = _counter(
    "industrial_rag_graph_requests_total",
    "LangGraph executions",
    ("intent", "status"),
)
GRAPH_DURATION = _histogram(
    "industrial_rag_graph_duration_seconds",
    "LangGraph execution duration",
    ("intent",),
)
NODE_EXECUTIONS = _counter(
    "industrial_rag_node_executions_total",
    "LangGraph node executions",
    ("node_name", "intent", "status"),
)
NODE_DURATION = _histogram(
    "industrial_rag_node_duration_seconds",
    "LangGraph node execution duration",
    ("node_name", "intent"),
)
MODEL_CALLS = _counter(
    "industrial_rag_model_calls_total",
    "LLM and embedding calls",
    ("provider", "model", "operation", "status"),
)
MODEL_DURATION = _histogram(
    "industrial_rag_model_duration_seconds",
    "LLM and embedding call duration",
    ("provider", "model", "operation"),
)
MODEL_INPUT_TOKENS = _counter(
    "industrial_rag_model_input_tokens_total",
    "Model input tokens reported by providers",
    ("provider", "model", "operation", "measurement_source"),
)
MODEL_OUTPUT_TOKENS = _counter(
    "industrial_rag_model_output_tokens_total",
    "Model output tokens reported by providers",
    ("provider", "model", "operation", "measurement_source"),
)
MODEL_COST = _counter(
    "industrial_rag_model_cost_total",
    "Calculated model cost at event time",
    ("provider", "model", "operation", "currency"),
)
PROMPT_INVOCATIONS = _counter(
    "industrial_rag_prompt_invocations_total",
    "Versioned prompt model invocations",
    ("prompt_id", "prompt_version", "component", "status"),
)
PROMPT_INVOCATION_DURATION = _histogram(
    "industrial_rag_prompt_invocation_duration_seconds",
    "Versioned prompt model invocation duration",
    ("prompt_id", "prompt_version", "component"),
)
PROMPT_RENDERS = _counter(
    "industrial_rag_prompt_renders_total",
    "Versioned prompt render attempts",
    ("prompt_id", "prompt_version", "component", "status"),
)
PROMPT_RENDER_DURATION = _histogram(
    "industrial_rag_prompt_render_duration_seconds",
    "Versioned prompt render duration",
    ("prompt_id", "prompt_version", "component"),
)
RETRIEVAL_REQUESTS = _counter(
    "industrial_rag_retrieval_requests_total",
    "Retrieval executions",
    ("retrieval_mode", "status"),
)
RETRIEVAL_DURATION = _histogram(
    "industrial_rag_retrieval_duration_seconds",
    "Retrieval duration",
    ("retrieval_mode",),
)
RETRIEVAL_DEGRADED = _counter(
    "industrial_rag_retrieval_degraded_total",
    "Retrieval operations that used degraded mode",
    ("retrieval_mode",),
)
USAGE_PERSIST_FAILURES = _counter(
    "industrial_rag_usage_persist_failures_total",
    "Usage analytics persistence failures",
    ("stage",),
)
DOCUMENT_OPERATIONS = _counter(
    "industrial_rag_document_operations_total",
    "Knowledge-base document lifecycle operations",
    ("operation", "status"),
)
DOCUMENT_OPERATION_DURATION = _histogram(
    "industrial_rag_document_operation_duration_seconds",
    "Knowledge-base document lifecycle operation duration",
    ("operation",),
)
RETRIEVAL_EVALUATION_RUNS = _counter(
    "industrial_rag_retrieval_evaluation_runs_total",
    "Retrieval-only evaluation runs",
    ("status",),
)
RETRIEVAL_EVALUATION_SCORE = _gauge(
    "industrial_rag_retrieval_evaluation_score",
    "Latest retrieval-only evaluation ranking score",
    ("metric", "k"),
)
RETRIEVAL_EVALUATION_LATENCY = _gauge(
    "industrial_rag_retrieval_evaluation_latency_ms",
    "Latest retrieval-only evaluation latency percentile in milliseconds",
    ("quantile",),
)


def _safe_label(value: str | None, default: str = "unknown") -> str:
    normalized = (value or default).strip().lower()
    return normalized[:80] or default


@contextmanager
def track_http_in_progress(method: str, route: str) -> Iterator[None]:
    labels = (_safe_label(method), _safe_label(route))
    if HTTP_IN_PROGRESS:
        HTTP_IN_PROGRESS.labels(*labels).inc()
    try:
        yield
    finally:
        if HTTP_IN_PROGRESS:
            HTTP_IN_PROGRESS.labels(*labels).dec()


def record_http_request(
    *, method: str, route: str, status_code: int, latency_ms: float
) -> None:
    status_class = f"{status_code // 100}xx"
    if HTTP_REQUESTS:
        HTTP_REQUESTS.labels(
            _safe_label(method), _safe_label(route), status_class
        ).inc()
    if HTTP_DURATION:
        HTTP_DURATION.labels(_safe_label(method), _safe_label(route)).observe(
            max(latency_ms, 0.0) / 1000
        )


def record_node_execution(
    *, node_name: str, intent: str | None, status: str, latency_ms: float
) -> None:
    labels = (
        _safe_label(node_name),
        _safe_label(intent),
        _safe_label(status),
    )
    if NODE_EXECUTIONS:
        NODE_EXECUTIONS.labels(*labels).inc()
    if NODE_DURATION:
        NODE_DURATION.labels(*labels[:2]).observe(max(latency_ms, 0.0) / 1000)


def record_graph_execution(
    *, intent: str | None, status: str, latency_ms: float
) -> None:
    if GRAPH_REQUESTS:
        GRAPH_REQUESTS.labels(_safe_label(intent), _safe_label(status)).inc()
    if GRAPH_DURATION:
        GRAPH_DURATION.labels(_safe_label(intent)).observe(
            max(latency_ms, 0.0) / 1000
        )


def record_model_usage(
    *,
    provider: str,
    model: str,
    operation: str,
    status: str,
    latency_ms: float,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    measurement_source: str = "unavailable",
    cost: float | None = None,
    currency: str | None = None,
) -> None:
    base_labels = (
        _safe_label(provider),
        _safe_label(model),
        _safe_label(operation),
    )
    if MODEL_CALLS:
        MODEL_CALLS.labels(*base_labels, _safe_label(status)).inc()
    if MODEL_DURATION:
        MODEL_DURATION.labels(*base_labels).observe(max(latency_ms, 0.0) / 1000)
    if input_tokens is not None and MODEL_INPUT_TOKENS:
        MODEL_INPUT_TOKENS.labels(
            *base_labels, _safe_label(measurement_source)
        ).inc(max(input_tokens, 0))
    if output_tokens is not None and MODEL_OUTPUT_TOKENS:
        MODEL_OUTPUT_TOKENS.labels(
            *base_labels, _safe_label(measurement_source)
        ).inc(max(output_tokens, 0))
    if cost is not None and MODEL_COST:
        MODEL_COST.labels(*base_labels, _safe_label(currency, "unknown")).inc(
            max(cost, 0.0)
        )


def record_prompt_invocation(
    *,
    prompt_id: str,
    prompt_version: str,
    component: str,
    status: str,
    latency_ms: float,
) -> None:
    labels = (
        _safe_label(prompt_id),
        _safe_label(prompt_version),
        _safe_label(component),
    )
    if PROMPT_INVOCATIONS:
        PROMPT_INVOCATIONS.labels(*labels, _safe_label(status)).inc()
    if PROMPT_INVOCATION_DURATION:
        PROMPT_INVOCATION_DURATION.labels(*labels).observe(
            max(latency_ms, 0.0) / 1000
        )


def record_prompt_render(
    *,
    prompt_id: str,
    prompt_version: str,
    component: str,
    status: str,
    latency_ms: float,
) -> None:
    labels = (
        _safe_label(prompt_id),
        _safe_label(prompt_version),
        _safe_label(component),
    )
    if PROMPT_RENDERS:
        PROMPT_RENDERS.labels(*labels, _safe_label(status)).inc()
    if PROMPT_RENDER_DURATION:
        PROMPT_RENDER_DURATION.labels(*labels).observe(
            max(latency_ms, 0.0) / 1000
        )


def record_retrieval(
    *, retrieval_mode: str, status: str, latency_ms: float, degraded: bool
) -> None:
    labels = (_safe_label(retrieval_mode), _safe_label(status))
    if RETRIEVAL_REQUESTS:
        RETRIEVAL_REQUESTS.labels(*labels).inc()
    if RETRIEVAL_DURATION:
        RETRIEVAL_DURATION.labels(labels[0]).observe(max(latency_ms, 0.0) / 1000)
    if degraded and RETRIEVAL_DEGRADED:
        RETRIEVAL_DEGRADED.labels(labels[0]).inc()


def record_usage_persist_failure(stage: str) -> None:
    if USAGE_PERSIST_FAILURES:
        USAGE_PERSIST_FAILURES.labels(_safe_label(stage)).inc()


def record_document_operation(
    *, operation: str, status: str, latency_ms: float
) -> None:
    operation_label = _safe_label(operation)
    if DOCUMENT_OPERATIONS:
        DOCUMENT_OPERATIONS.labels(operation_label, _safe_label(status)).inc()
    if DOCUMENT_OPERATION_DURATION:
        DOCUMENT_OPERATION_DURATION.labels(operation_label).observe(
            max(latency_ms, 0.0) / 1000
        )


def record_retrieval_evaluation(
    *,
    status: str,
    metrics: dict[str, float],
    latency: dict[str, object],
    increment_run: bool = True,
) -> None:
    if RETRIEVAL_EVALUATION_RUNS and increment_run:
        RETRIEVAL_EVALUATION_RUNS.labels(_safe_label(status)).inc()
    if RETRIEVAL_EVALUATION_SCORE:
        RETRIEVAL_EVALUATION_SCORE.clear()
        for name, value in metrics.items():
            metric_name, separator, k_value = name.partition("@")
            if not separator or not k_value.isdigit():
                continue
            RETRIEVAL_EVALUATION_SCORE.labels(
                _safe_label(metric_name), k_value
            ).set(float(value))
    if RETRIEVAL_EVALUATION_LATENCY:
        RETRIEVAL_EVALUATION_LATENCY.clear()
        total = latency.get("retrieval_total", {})
        if isinstance(total, dict):
            for quantile in ("p50", "p95", "p99"):
                value = total.get(f"{quantile}_ms")
                if value is not None:
                    RETRIEVAL_EVALUATION_LATENCY.labels(quantile).set(
                        max(float(value), 0.0)
                    )


def render_metrics() -> tuple[bytes, str]:
    if not _METRICS_ENABLED:
        return b"# metrics are disabled\n", CONTENT_TYPE_LATEST
    if generate_latest is None:
        return b"# prometheus_client is not installed\n", CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST
