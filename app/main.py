import asyncio
from uuid import uuid4
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes_auth import router as auth_router
from app.api.routes_audit import router as audit_router
from app.api.routes_chat import router as chat_router
from app.api.routes_documents import router as documents_router
from app.api.routes_evaluation import router as evaluation_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_observability import router as observability_router
from app.core.logger import log_business_event
from app.core.config import settings
from app.core.metrics import (
    record_http_request,
    record_usage_persist_failure,
    render_metrics,
    track_http_in_progress,
)
from app.core.telemetry import get_current_trace_ids, initialize_telemetry
from app.core.telemetry_context import (
    complete_request_context,
    reset_request_context,
    start_request_context,
    update_request_context,
)
from app.db.session import engine
from app.rag.opensearch_client import get_opensearch_client
from app.rag.qdrant_client import get_qdrant_client
from app.prompting import get_prompt_registry
from app.services.usage_service import UsageService


usage_service = UsageService()
_usage_persistence_tasks: set[asyncio.Task] = set()
_usage_persistence_semaphore = asyncio.Semaphore(
    max(settings.usage_background_workers, 1)
)


async def _persist_usage_in_background(context) -> None:
    async with _usage_persistence_semaphore:
        await asyncio.to_thread(usage_service.safe_persist_context, context)


def _schedule_usage_persistence(context) -> None:
    if context is None:
        return
    max_pending = max(settings.usage_background_max_pending, 1)
    if len(_usage_persistence_tasks) >= max_pending:
        record_usage_persist_failure("queue_full")
        log_business_event(
            "usage_persist_queue_full",
            request_id=context.request_id,
            session_id=context.session_id,
            status="failed",
            error_message="usage persistence queue reached its configured limit",
            pending_task_count=len(_usage_persistence_tasks),
        )
        return
    task = asyncio.create_task(_persist_usage_in_background(context))
    _usage_persistence_tasks.add(task)
    task.add_done_callback(_usage_persistence_tasks.discard)


app = FastAPI(
    title="Industrial Quality Agentic RAG Assistant",
    description="工业质量知识库与设备异常诊断 RAG 系统",
    version="0.1.0"
)


@app.on_event("startup")
def validate_active_prompt_release() -> None:
    if not settings.prompt_validate_on_startup:
        log_business_event(
            "prompt_registry_startup_validation_skipped",
            status="success",
        )
        return
    registry = get_prompt_registry()
    metadata = registry.release_metadata()
    log_business_event(
        "prompt_registry_startup_validated",
        status="success",
        prompt_release=metadata["release_id"],
        prompt_channel=metadata["channel"],
        prompt_count=len(metadata["versions"]),
    )


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    started_at = perf_counter()
    token = start_request_context(
        request_id,
        route=request.url.path,
        method=request.method,
    )
    status_code = 500
    error_type = None

    try:
        with track_http_in_progress(request.method, "all"):
            response = await call_next(request)
        status_code = response.status_code
        route = request.scope.get("route")
        route_template = getattr(route, "path", request.url.path)
        update_request_context(route=route_template)
        trace_id, _ = get_current_trace_ids()
        update_request_context(trace_id=trace_id)
        response.headers["X-Request-ID"] = request_id
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        return response
    except Exception as exc:
        error_type = type(exc).__name__
        log_business_event(
            "http_request_failed",
            request_id=request_id,
            status="failed",
            error_message=str(exc),
            method=request.method,
            route=request.url.path,
            error_type=error_type,
        )
        raise
    finally:
        latency_ms = (perf_counter() - started_at) * 1000
        route = request.scope.get("route")
        route_template = getattr(route, "path", request.url.path)
        request_status = (
            "success"
            if status_code < 400
            else "denied"
            if status_code in {401, 403}
            else "client_error"
            if status_code < 500
            else "failed"
        )
        context = complete_request_context(
            status=request_status,
            http_status=status_code,
            total_latency_ms=latency_ms,
            error_type=error_type,
        )
        record_http_request(
            method=request.method,
            route=route_template,
            status_code=status_code,
            latency_ms=latency_ms,
        )
        log_business_event(
            "http_request_completed",
            request_id=request_id,
            status=request_status,
            latency_ms=latency_ms,
            method=request.method,
            route=route_template,
            http_status=status_code,
            error_type=error_type,
        )
        if context is not None and (
            route_template == "/api/v1/graph-chat"
            or context.ai_events
            or context.retrieval_events
        ):
            _schedule_usage_persistence(context)
        reset_request_context(token)


@app.on_event("shutdown")
async def drain_usage_persistence_tasks() -> None:
    if not _usage_persistence_tasks:
        return
    try:
        await asyncio.wait_for(
            asyncio.gather(*tuple(_usage_persistence_tasks)),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        log_business_event(
            "usage_persist_shutdown_timeout",
            status="failed",
            error_message="usage persistence tasks exceeded shutdown timeout",
            pending_task_count=len(_usage_persistence_tasks),
        )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/live", include_in_schema=False)
def liveness_check():
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
def readiness_check():
    checks: dict[str, dict[str, object]] = {}

    try:
        with engine.connect() as connection:
            usage_table = connection.execute(
                text("SELECT to_regclass('public.rag_request_runs')")
            ).scalar_one()
            if usage_table is None:
                raise RuntimeError("rag_request_runs table is not initialized")
        checks["postgresql"] = {"status": "ready"}
    except Exception as exc:
        checks["postgresql"] = {
            "status": "unavailable",
            "error_type": type(exc).__name__,
        }

    try:
        get_qdrant_client().get_collection(settings.qdrant_collection_alias)
        checks["qdrant"] = {"status": "ready"}
    except Exception as exc:
        checks["qdrant"] = {
            "status": "unavailable",
            "error_type": type(exc).__name__,
        }

    config_ready = bool(
        settings.llm_api_key
        and (
            settings.embedding_provider != "qwen"
            or settings.qwen_embedding_api_key
        )
    )
    checks["model_configuration"] = {
        "status": "ready" if config_ready else "unavailable"
    }

    try:
        prompt_metadata = get_prompt_registry().release_metadata()
        checks["prompt_registry"] = {
            "status": "ready",
            "release_id": prompt_metadata["release_id"],
            "channel": prompt_metadata["channel"],
        }
    except Exception as exc:
        checks["prompt_registry"] = {
            "status": "unavailable",
            "error_type": type(exc).__name__,
        }

    try:
        opensearch_ready = bool(get_opensearch_client().ping())
        checks["opensearch"] = {
            "status": "ready" if opensearch_ready else "unavailable"
        }
    except Exception as exc:
        checks["opensearch"] = {
            "status": "unavailable",
            "error_type": type(exc).__name__,
        }

    critical_ready = all(
        checks[name]["status"] == "ready"
        for name in (
            "postgresql",
            "qdrant",
            "model_configuration",
            "prompt_registry",
        )
    )
    opensearch_ready = checks["opensearch"]["status"] == "ready"
    status = (
        "ready"
        if critical_ready and opensearch_ready
        else "degraded"
        if critical_ready
        else "not_ready"
    )
    response_status = 200 if critical_ready else 503
    return JSONResponse(
        status_code=response_status,
        content={"status": status, "checks": checks},
    )


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint():
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(feedback_router)
app.include_router(evaluation_router)
app.include_router(observability_router)


initialize_telemetry(app=app, engine=engine)
