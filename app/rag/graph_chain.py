from time import perf_counter
from uuid import uuid4

from app.core.logger import log_node_event
from app.core.metrics import record_graph_execution
from app.core.telemetry import get_current_trace_ids, traced_span
from app.core.telemetry_context import (
    complete_request_context,
    get_request_context,
    reset_request_context,
    start_request_context,
    update_request_context,
)
from app.graph.workflow import industrial_rag_app
from app.graph.state import RetrievalMode
from app.core.config import settings
from app.prompting import get_prompt_registry
from app.observability.request_diagnostics import build_diagnostic_snapshot
from app.services.usage_service import UsageService


usage_service = UsageService()


class IndustrialGraphRAGChain:
    def invoke(
        self,
        question: str,
        top_k: int = 5,
        session_id: str = "default",
        request_id: str | None = None,
        user: dict | None = None,
        retrieval_filters: dict[str, list[str]] | None = None,
        multimodal_query: dict | None = None,
        retrieval_mode: RetrievalMode = "knowledge",
        memory_enabled: bool = True,
    ) -> dict:
        request_id = request_id or str(uuid4())
        session_id = session_id or "default"
        owns_usage_context = get_request_context() is None
        context_token = None
        if owns_usage_context:
            context_token = start_request_context(
                request_id,
                route="internal.graph_chat",
                method="INTERNAL",
            )
        update_request_context(
            session_id=session_id,
            username=(user or {}).get("username"),
            role=(user or {}).get("role"),
        )
        initial_state = {
            "question": question,
            "request_id": request_id,
            "session_id": session_id,
            "user": user,
            "memory_enabled": memory_enabled,
            "memory_messages": [],
            "memory_metadata": {},
            "knowledge_graph_metadata": {},
            "retrieval_filters": retrieval_filters,
            "multimodal_query": multimodal_query,
            "requested_retrieval_mode": retrieval_mode,
            "intent": "rag",
            "query_features": {},
            "rewritten_query": "",
            "contexts": [],
            "generation_contexts": [],
            "generation_context_metadata": {},
            "answer": "",
            "citations": [],
            "retrieval_metadata": {},
            "retrieval_diagnostics": {},
            "evidence_score": 0.0,
            "evidence_enough": False,
            "evidence_confidence": 0.0,
            "evidence_reasons": [],
            "missing_aspects": [],
            "abstain_reason": None,
            "answer_abstained": False,
            "draft_answer": "",
            "generation_retry_count": 0,
            "generation_repair_error": None,
            "answer_validation": {},
            "answer_validation_history": [],
            "answer_structure": {},
            "generation_quality_passed": False,
            "citation_pruned": False,
            "retry_count": 0,
            "top_k": top_k,
            "rule_result": None,
            "sql_result": None,
            "case_result": None,
        }
        started_at = perf_counter()
        graph_trace_id: str | None = None
        prompt_release_metadata: dict = {}

        try:
            prompt_release_metadata = get_prompt_registry().release_metadata()
            update_request_context(
                prompt_release=prompt_release_metadata["release_id"],
                prompt_versions=prompt_release_metadata["versions"],
            )
            with traced_span(
                "rag.graph_chat",
                attributes={
                    "rag.request_id": request_id,
                    "rag.session_id": session_id,
                    "rag.top_k": top_k,
                    "rag.requested_retrieval_mode": retrieval_mode,
                    "rag.prompt.release": prompt_release_metadata["release_id"],
                },
            ):
                graph_trace_id, _ = get_current_trace_ids()
                result = industrial_rag_app.invoke(initial_state)
        except Exception as exc:
            total_latency_ms = (perf_counter() - started_at) * 1000
            log_node_event(
                state=initial_state,
                node_name="graph_chat",
                latency_ms=total_latency_ms,
                status="error",
                error=str(exc),
                exc_info=True,
            )
            record_graph_execution(
                intent=initial_state.get("intent"),
                status="failed",
                latency_ms=total_latency_ms,
            )
            trace_id = graph_trace_id
            active_context = get_request_context()
            context = update_request_context(
                trace_id=trace_id,
                intent=initial_state.get("intent"),
                diagnostic_snapshot=build_diagnostic_snapshot(
                    initial_state,
                    prompt_release=prompt_release_metadata,
                    status="failed",
                    error_type=type(exc).__name__,
                    workflow_events=(
                        active_context.workflow_events
                        if active_context is not None
                        else []
                    ),
                ),
            )
            complete_request_context(
                status="failed",
                total_latency_ms=total_latency_ms,
                error_type=type(exc).__name__,
            )
            if owns_usage_context:
                usage_service.safe_persist_context(context)
                if context_token is not None:
                    reset_request_context(context_token)
            raise

        total_latency_ms = round((perf_counter() - started_at) * 1000, 2)
        metadata = {
            "intent": result.get("intent"),
            "evidence_score": result.get("evidence_score"),
            "evidence_enough": result.get("evidence_enough"),
            "evidence_confidence": result.get("evidence_confidence"),
            "evidence_reasons": result.get("evidence_reasons", []),
            "missing_aspects": result.get("missing_aspects", []),
            "abstain_reason": result.get("abstain_reason"),
            "answer_abstained": result.get("answer_abstained", False),
            "generation_retry_count": result.get("generation_retry_count", 0),
            "generation_repair_error": result.get("generation_repair_error"),
            "generation_quality_passed": result.get(
                "generation_quality_passed", False
            ),
            "answer_validation": result.get("answer_validation", {}),
            "answer_validation_history": result.get(
                "answer_validation_history", []
            ),
            "answer_structure": result.get("answer_structure", {}),
            "citation_pruned": result.get("citation_pruned", False),
            "retry_count": result.get("retry_count"),
            "query_features": result.get("query_features", {}),
            "requested_retrieval_mode": result.get(
                "requested_retrieval_mode",
                retrieval_mode,
            ),
            "total_latency_ms": total_latency_ms,
        }
        metadata.update(result.get("retrieval_metadata", {}))
        metadata.update(result.get("generation_context_metadata", {}))
        metadata.update(result.get("memory_metadata", {}))
        metadata.update(result.get("knowledge_graph_metadata", {}))
        if settings.prompt_expose_version_in_response:
            metadata["prompt_release"] = prompt_release_metadata["release_id"]
            metadata["prompt_versions"] = prompt_release_metadata["versions"]
        trace_id = graph_trace_id
        if trace_id:
            metadata["trace_id"] = trace_id

        retrieval_metadata = result.get("retrieval_metadata", {})
        active_context = get_request_context()
        context = update_request_context(
            trace_id=trace_id,
            intent=result.get("intent"),
            evidence_score=result.get("evidence_score"),
            evidence_enough=result.get("evidence_enough"),
            retry_count=result.get("retry_count", 0),
            retrieval_mode=retrieval_metadata.get("retrieval_mode"),
            degraded=bool(retrieval_metadata.get("degraded", False)),
            degraded_reason=retrieval_metadata.get("degraded_reason"),
            context_count=len(result.get("contexts", [])),
            citation_count=len(result.get("citations", [])),
            diagnostic_snapshot=build_diagnostic_snapshot(
                result,
                prompt_release=prompt_release_metadata,
                workflow_events=(
                    active_context.workflow_events
                    if active_context is not None
                    else []
                ),
            ),
        )
        context = complete_request_context(
            status="success",
            total_latency_ms=total_latency_ms,
        ) or context
        if context is not None:
            metadata["usage"] = {
                "llm_call_count": sum(
                    1
                    for event in context.ai_events
                    if event.operation == "chat_completion"
                ),
                "input_tokens": context.input_tokens,
                "output_tokens": context.output_tokens,
                "total_tokens": context.total_tokens,
                "embedding_tokens": context.embedding_tokens,
                "calculated_cost": context.estimated_cost,
            }

        log_node_event(
            state=result,
            node_name="graph_chat",
            latency_ms=total_latency_ms,
            status="success",
            intent=result.get("intent"),
        )
        record_graph_execution(
            intent=result.get("intent"),
            status="success",
            latency_ms=total_latency_ms,
        )

        if owns_usage_context:
            usage_service.safe_persist_context(context)
            if context_token is not None:
                reset_request_context(context_token)

        return {
            "question": result.get("question", question),
            "answer": result.get("answer", ""),
            "citations": result.get("citations", []),
            "request_id": result.get("request_id", request_id),
            "session_id": result.get("session_id", session_id),
            "memory_messages": result.get("memory_messages", []),
            "metadata": metadata,

            "intent": result.get("intent"),
            "retrieval_mode": result.get(
                "requested_retrieval_mode",
                retrieval_mode,
            ),
            "task_mode": (result.get("query_features") or {}).get("task_mode"),
            "query_plan": result.get("query_features", {}),
            "rewritten_query": result.get("rewritten_query"),
            "evidence_score": result.get("evidence_score"),
            "evidence_enough": result.get("evidence_enough"),
            "retry_count": result.get("retry_count"),

            "rule_result": result.get("rule_result"),
            "sql_result": result.get("sql_result"),
            "case_result": result.get("case_result"),
            "contexts": result.get("contexts", []),
        }
