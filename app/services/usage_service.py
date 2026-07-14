from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.logger import log_business_event
from app.core.metrics import record_usage_persist_failure
from app.core.sensitive_filter import sanitize_telemetry_value
from app.db.session import engine
from app.observability.usage_models import RequestUsageContext


class UsageService:
    def __init__(self, database_engine: Engine | None = None) -> None:
        self.engine = database_engine or engine

    def persist_context(self, context: RequestUsageContext) -> None:
        if not settings.usage_analytics_enabled:
            return

        currencies = {
            event.currency for event in context.ai_events if event.currency
        }
        currency = next(iter(currencies)) if len(currencies) == 1 else (
            "mixed" if currencies else None
        )
        request_payload = {
            "request_id": context.request_id,
            "trace_id": context.trace_id,
            "session_id": context.session_id,
            "username": context.username,
            "role": context.role,
            "route": context.route,
            "method": context.method,
            "intent": context.intent,
            "status": context.status,
            "http_status": context.http_status,
            "total_latency_ms": context.total_latency_ms,
            "evidence_score": context.evidence_score,
            "evidence_enough": context.evidence_enough,
            "retry_count": context.retry_count,
            "retrieval_mode": context.retrieval_mode,
            "degraded": context.degraded,
            "degraded_reason": sanitize_telemetry_value(
                context.degraded_reason
            ),
            "context_count": context.context_count,
            "citation_count": context.citation_count,
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
            "currency": currency,
            "error_type": context.error_type,
            "metadata": self._json_dumps(context.attributes),
            "started_at": context.started_at,
            "completed_at": context.completed_at,
        }

        with self.engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO rag_request_runs (
                        request_id, trace_id, session_id, username, role,
                        route, method, intent, status, http_status,
                        total_latency_ms, evidence_score, evidence_enough,
                        retry_count, retrieval_mode, degraded,
                        degraded_reason, context_count, citation_count,
                        llm_call_count, input_tokens, output_tokens,
                        total_tokens, embedding_tokens, calculated_cost,
                        currency, error_type, metadata, started_at, completed_at
                    ) VALUES (
                        :request_id, :trace_id, :session_id, :username, :role,
                        :route, :method, :intent, :status, :http_status,
                        :total_latency_ms, :evidence_score, :evidence_enough,
                        :retry_count, :retrieval_mode, :degraded,
                        :degraded_reason, :context_count, :citation_count,
                        :llm_call_count, :input_tokens, :output_tokens,
                        :total_tokens, :embedding_tokens, :calculated_cost,
                        :currency, :error_type, :metadata, :started_at,
                        :completed_at
                    )
                    ON CONFLICT (request_id) DO UPDATE SET
                        trace_id = EXCLUDED.trace_id,
                        session_id = EXCLUDED.session_id,
                        username = EXCLUDED.username,
                        role = EXCLUDED.role,
                        route = EXCLUDED.route,
                        method = EXCLUDED.method,
                        intent = EXCLUDED.intent,
                        status = EXCLUDED.status,
                        http_status = EXCLUDED.http_status,
                        total_latency_ms = EXCLUDED.total_latency_ms,
                        evidence_score = EXCLUDED.evidence_score,
                        evidence_enough = EXCLUDED.evidence_enough,
                        retry_count = EXCLUDED.retry_count,
                        retrieval_mode = EXCLUDED.retrieval_mode,
                        degraded = EXCLUDED.degraded,
                        degraded_reason = EXCLUDED.degraded_reason,
                        context_count = EXCLUDED.context_count,
                        citation_count = EXCLUDED.citation_count,
                        llm_call_count = EXCLUDED.llm_call_count,
                        input_tokens = EXCLUDED.input_tokens,
                        output_tokens = EXCLUDED.output_tokens,
                        total_tokens = EXCLUDED.total_tokens,
                        embedding_tokens = EXCLUDED.embedding_tokens,
                        calculated_cost = EXCLUDED.calculated_cost,
                        currency = EXCLUDED.currency,
                        error_type = EXCLUDED.error_type,
                        metadata = EXCLUDED.metadata,
                        completed_at = EXCLUDED.completed_at,
                        updated_at = NOW()
                """),
                request_payload,
            )

            if context.ai_events:
                connection.execute(
                    text("""
                        INSERT INTO ai_usage_events (
                            event_id, request_id, trace_id, component,
                            operation, provider, model, status, latency_ms,
                            input_tokens, output_tokens, total_tokens,
                            input_text_count, input_char_count, cost, currency,
                            pricing_version, measurement_source, error_type,
                            metadata, created_at
                        ) VALUES (
                            :event_id, :request_id, :trace_id, :component,
                            :operation, :provider, :model, :status, :latency_ms,
                            :input_tokens, :output_tokens, :total_tokens,
                            :input_text_count, :input_char_count, :cost,
                            :currency, :pricing_version, :measurement_source,
                            :error_type, :metadata, :created_at
                        )
                        ON CONFLICT (event_id) DO NOTHING
                    """),
                    [
                        {
                            "event_id": event.event_id,
                            "request_id": context.request_id,
                            "trace_id": context.trace_id,
                            "component": event.component,
                            "operation": event.operation,
                            "provider": event.provider,
                            "model": event.model,
                            "status": event.status,
                            "latency_ms": event.latency_ms,
                            "input_tokens": event.input_tokens,
                            "output_tokens": event.output_tokens,
                            "total_tokens": event.total_tokens,
                            "input_text_count": event.input_text_count,
                            "input_char_count": event.input_char_count,
                            "cost": event.cost,
                            "currency": event.currency,
                            "pricing_version": event.pricing_version,
                            "measurement_source": event.measurement_source,
                            "error_type": event.error_type,
                            "metadata": self._json_dumps(event.metadata),
                            "created_at": event.created_at,
                        }
                        for event in context.ai_events
                    ],
                )

            if context.retrieval_events:
                connection.execute(
                    text("""
                        INSERT INTO retrieval_events (
                            event_id, request_id, trace_id, operation, status,
                            latency_ms, top_k, vector_hit_count,
                            keyword_hit_count, fused_hit_count, returned_count,
                            reranker_used, retrieval_mode, degraded,
                            degraded_reason, qdrant_latency_ms,
                            opensearch_latency_ms, fusion_latency_ms,
                            reranker_latency_ms, collection_name, keyword_index,
                            embedding_index_version, error_type, query_hash,
                            metadata, created_at
                        ) VALUES (
                            :event_id, :request_id, :trace_id, :operation,
                            :status, :latency_ms, :top_k, :vector_hit_count,
                            :keyword_hit_count, :fused_hit_count,
                            :returned_count, :reranker_used, :retrieval_mode,
                            :degraded, :degraded_reason, :qdrant_latency_ms,
                            :opensearch_latency_ms, :fusion_latency_ms,
                            :reranker_latency_ms, :collection_name,
                            :keyword_index, :embedding_index_version,
                            :error_type, :query_hash, :metadata, :created_at
                        )
                        ON CONFLICT (event_id) DO NOTHING
                    """),
                    [
                        {
                            "event_id": event.event_id,
                            "request_id": context.request_id,
                            "trace_id": context.trace_id,
                            "operation": event.operation,
                            "status": event.status,
                            "latency_ms": event.latency_ms,
                            "top_k": event.top_k,
                            "vector_hit_count": event.vector_hit_count,
                            "keyword_hit_count": event.keyword_hit_count,
                            "fused_hit_count": event.fused_hit_count,
                            "returned_count": event.returned_count,
                            "reranker_used": event.reranker_used,
                            "retrieval_mode": event.retrieval_mode,
                            "degraded": event.degraded,
                            "degraded_reason": sanitize_telemetry_value(
                                event.degraded_reason
                            ),
                            "qdrant_latency_ms": event.qdrant_latency_ms,
                            "opensearch_latency_ms": event.opensearch_latency_ms,
                            "fusion_latency_ms": event.fusion_latency_ms,
                            "reranker_latency_ms": event.reranker_latency_ms,
                            "collection_name": event.collection_name,
                            "keyword_index": event.keyword_index,
                            "embedding_index_version": event.embedding_index_version,
                            "error_type": event.error_type,
                            "query_hash": event.metadata.get("query_hash"),
                            "metadata": self._json_dumps(event.metadata),
                            "created_at": event.created_at,
                        }
                        for event in context.retrieval_events
                    ],
                )

    def safe_persist_context(self, context: RequestUsageContext | None) -> bool:
        if context is None or not settings.usage_analytics_enabled:
            return False
        try:
            self.persist_context(context)
            log_business_event(
                "usage_persisted",
                request_id=context.request_id,
                session_id=context.session_id,
                username=context.username,
                role=context.role,
                status="success",
                ai_event_count=len(context.ai_events),
                retrieval_event_count=len(context.retrieval_events),
                total_tokens=context.total_tokens,
            )
            return True
        except Exception as exc:
            record_usage_persist_failure("postgresql")
            log_business_event(
                "usage_persist_failed",
                request_id=context.request_id,
                session_id=context.session_id,
                username=context.username,
                role=context.role,
                status="failed",
                error_message=str(exc),
                error_type=type(exc).__name__,
            )
            return False

    def get_request_details(self, request_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            run = connection.execute(
                text("SELECT * FROM rag_request_runs WHERE request_id = :request_id"),
                {"request_id": request_id},
            ).mappings().first()
            if run is None:
                return None
            ai_events = connection.execute(
                text("""
                    SELECT * FROM ai_usage_events
                    WHERE request_id = :request_id ORDER BY id
                """),
                {"request_id": request_id},
            ).mappings().all()
            retrieval_events = connection.execute(
                text("""
                    SELECT * FROM retrieval_events
                    WHERE request_id = :request_id ORDER BY id
                """),
                {"request_id": request_id},
            ).mappings().all()
        return {
            "request": self._deserialize_row(dict(run)),
            "ai_events": [self._deserialize_row(dict(row)) for row in ai_events],
            "retrieval_events": [
                self._deserialize_row(dict(row)) for row in retrieval_events
            ],
        }

    def cleanup_old_data(self, retention_days: int | None = None) -> dict[str, int]:
        days = (
            settings.usage_retention_days
            if retention_days is None
            else retention_days
        )
        if days <= 0:
            raise ValueError("retention_days must be greater than zero")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self.engine.begin() as connection:
            ai_result = connection.execute(
                text("DELETE FROM ai_usage_events WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            retrieval_result = connection.execute(
                text("DELETE FROM retrieval_events WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            request_result = connection.execute(
                text("DELETE FROM rag_request_runs WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
        result = {
            "ai_usage_events": max(ai_result.rowcount or 0, 0),
            "retrieval_events": max(retrieval_result.rowcount or 0, 0),
            "rag_request_runs": max(request_result.rowcount or 0, 0),
        }
        log_business_event(
            "usage_retention_cleanup_completed",
            status="success",
            retention_days=days,
            cutoff=cutoff.isoformat(),
            **result,
        )
        return result

    def get_overview(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, Any]:
        where_clause, params = self._time_filter(start_at, end_at)
        query = text(f"""
            SELECT
                COUNT(*) AS total_requests,
                COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE status <> 'success') AS failed_count,
                COALESCE(AVG(total_latency_ms), 0) AS avg_latency_ms,
                COALESCE(
                    percentile_cont(0.95) WITHIN GROUP (
                        ORDER BY total_latency_ms
                    ) FILTER (WHERE total_latency_ms IS NOT NULL),
                    0
                ) AS p95_latency_ms,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(embedding_tokens), 0) AS embedding_tokens,
                COALESCE(SUM(calculated_cost), 0) AS calculated_cost,
                STRING_AGG(DISTINCT currency, ',')
                    FILTER (WHERE currency IS NOT NULL) AS currency,
                COUNT(*) FILTER (WHERE degraded = true) AS degraded_count,
                COUNT(*) FILTER (WHERE evidence_enough = true)
                    AS evidence_enough_count
            FROM rag_request_runs
            {where_clause}
        """)
        with self.engine.connect() as connection:
            row = connection.execute(query, params).mappings().one()
        result = dict(row)
        total = int(result.get("total_requests") or 0)
        result["success_rate"] = (
            round(int(result.get("success_count") or 0) / total, 4)
            if total
            else 0.0
        )
        result["degraded_rate"] = (
            round(int(result.get("degraded_count") or 0) / total, 4)
            if total
            else 0.0
        )
        return result

    def get_timeseries(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        granularity: str = "day",
    ) -> list[dict[str, Any]]:
        date_part = {"hour": "hour", "day": "day"}.get(granularity)
        if date_part is None:
            raise ValueError("granularity must be 'hour' or 'day'")
        where_clause, params = self._time_filter(start_at, end_at)
        query = text(f"""
            SELECT
                date_trunc('{date_part}', created_at) AS bucket,
                COUNT(*) AS request_count,
                COUNT(*) FILTER (WHERE status <> 'success') AS failed_count,
                COALESCE(AVG(total_latency_ms), 0) AS avg_latency_ms,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(calculated_cost), 0) AS calculated_cost,
                COUNT(*) FILTER (WHERE degraded = true) AS degraded_count
            FROM rag_request_runs
            {where_clause}
            GROUP BY bucket
            ORDER BY bucket
        """)
        with self.engine.connect() as connection:
            rows = connection.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    def get_model_usage(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._time_filter(
            start_at,
            end_at,
            column="created_at",
        )
        query = text(f"""
            SELECT provider, model, operation, currency,
                COUNT(*) AS call_count,
                COUNT(*) FILTER (WHERE status <> 'success') AS failed_count,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(cost), 0) AS calculated_cost
            FROM ai_usage_events
            {where_clause}
            GROUP BY provider, model, operation, currency
            ORDER BY call_count DESC
        """)
        with self.engine.connect() as connection:
            rows = connection.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    def get_intent_usage(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._time_filter(start_at, end_at)
        query = text(f"""
            SELECT COALESCE(intent, 'unknown') AS intent,
                COUNT(*) AS request_count,
                COUNT(*) FILTER (WHERE status <> 'success') AS failed_count,
                COALESCE(AVG(total_latency_ms), 0) AS avg_latency_ms,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(calculated_cost), 0) AS calculated_cost
            FROM rag_request_runs
            {where_clause}
            GROUP BY COALESCE(intent, 'unknown')
            ORDER BY request_count DESC
        """)
        with self.engine.connect() as connection:
            rows = connection.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    def get_retrieval_usage(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._time_filter(start_at, end_at)
        query = text(f"""
            SELECT COALESCE(retrieval_mode, 'unknown') AS retrieval_mode,
                COUNT(*) AS request_count,
                COUNT(*) FILTER (WHERE degraded = true) AS degraded_count,
                COUNT(*) FILTER (WHERE status <> 'success') AS failed_count,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                COALESCE(AVG(qdrant_latency_ms), 0) AS avg_qdrant_latency_ms,
                COALESCE(AVG(opensearch_latency_ms), 0)
                    AS avg_opensearch_latency_ms,
                COALESCE(AVG(returned_count), 0) AS avg_returned_count
            FROM retrieval_events
            {where_clause}
            GROUP BY COALESCE(retrieval_mode, 'unknown')
            ORDER BY request_count DESC
        """)
        with self.engine.connect() as connection:
            rows = connection.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def _time_filter(
        start_at: datetime | None,
        end_at: datetime | None,
        *,
        column: str = "created_at",
    ) -> tuple[str, dict[str, Any]]:
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if start_at is not None:
            conditions.append(f"{column} >= :start_at")
            params["start_at"] = start_at
        if end_at is not None:
            conditions.append(f"{column} <= :end_at")
            params["end_at"] = end_at
        return (
            "WHERE " + " AND ".join(conditions) if conditions else "",
            params,
        )

    @staticmethod
    def _json_dumps(payload: dict[str, Any]) -> str:
        return json.dumps(
            sanitize_telemetry_value(payload),
            ensure_ascii=False,
            default=str,
        )

    @staticmethod
    def _deserialize_row(row: dict[str, Any]) -> dict[str, Any]:
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            try:
                row["metadata"] = json.loads(metadata)
            except json.JSONDecodeError:
                pass
        return row
