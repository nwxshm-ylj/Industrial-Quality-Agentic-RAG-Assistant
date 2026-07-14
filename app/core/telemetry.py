from __future__ import annotations

from contextlib import contextmanager
import os
import logging
from threading import Lock
from typing import Any, Iterator

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    from opentelemetry.trace import Status, StatusCode
except ImportError:  # pragma: no cover - dependencies are installed in Docker
    trace = None
    OTLPSpanExporter = None
    FastAPIInstrumentor = RequestsInstrumentor = SQLAlchemyInstrumentor = None
    Resource = TracerProvider = BatchSpanProcessor = None
    ParentBased = TraceIdRatioBased = None
    Status = StatusCode = None


_initialization_lock = Lock()
_initialized = False
_sqlalchemy_instrumented = False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _telemetry_enabled() -> bool:
    return _env_bool("TELEMETRY_ENABLED", True)


def _service_name() -> str:
    return os.getenv("OTEL_SERVICE_NAME", "industrial-quality-rag-api")


class NoopSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None

    def set_status(self, status: Any) -> None:
        return None


def _initialize_telemetry(app: Any | None = None, engine: Any | None = None) -> bool:
    global _initialized, _sqlalchemy_instrumented

    if not _telemetry_enabled() or trace is None:
        return False

    with _initialization_lock:
        if not _initialized:
            resource = Resource.create(
                {
                    "service.name": _service_name(),
                    "service.version": os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
                    "deployment.environment": os.getenv(
                        "ENVIRONMENT", "development"
                    ),
                }
            )
            sampler = ParentBased(
                TraceIdRatioBased(
                    min(
                        max(float(os.getenv("OTEL_TRACE_SAMPLE_RATIO", "1.0")), 0.0),
                        1.0,
                    )
                )
            )
            provider = TracerProvider(resource=resource, sampler=sampler)
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
            if otlp_endpoint:
                exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint.rstrip("/") + "/v1/traces",
                    timeout=float(os.getenv("OTEL_EXPORT_TIMEOUT_SECONDS", "5")),
                )
                provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            if RequestsInstrumentor:
                RequestsInstrumentor().instrument()
            _initialized = True

        if app is not None and FastAPIInstrumentor:
            FastAPIInstrumentor.instrument_app(
                app,
                excluded_urls="/health,/health/live,/metrics",
            )
        if engine is not None and SQLAlchemyInstrumentor and not _sqlalchemy_instrumented:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            _sqlalchemy_instrumented = True
    return True


def initialize_telemetry(app: Any | None = None, engine: Any | None = None) -> bool:
    try:
        return _initialize_telemetry(app=app, engine=engine)
    except Exception:
        logging.getLogger("industrial_rag.telemetry").exception(
            "telemetry_initialization_failed"
        )
        return False


def get_current_trace_ids() -> tuple[str | None, str | None]:
    if trace is None:
        return None, None
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None, None
    return f"{span_context.trace_id:032x}", f"{span_context.span_id:016x}"


@contextmanager
def traced_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    if not _telemetry_enabled() or trace is None:
        yield NoopSpan()
        return

    tracer = trace.get_tracer(_service_name())
    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            if value is not None and isinstance(value, (str, bool, int, float)):
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            if Status and StatusCode:
                span.set_status(Status(StatusCode.ERROR, str(exc)[:256]))
            raise
