from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text

from app.db.session import engine
from app.observability.usage_models import (
    AIUsageEvent,
    RequestUsageContext,
    RetrievalUsageEvent,
)
from app.services.usage_service import UsageService


def main() -> None:
    request_id = f"usage-test-{uuid4().hex}"
    service = UsageService()
    context = RequestUsageContext(
        request_id=request_id,
        session_id="usage-test-session",
        username="admin",
        role="admin",
        route="internal.test",
        method="TEST",
        intent="doc_qa",
        status="success",
        total_latency_ms=42.0,
        evidence_score=0.8,
        evidence_enough=True,
        context_count=2,
        citation_count=2,
    )
    context.completed_at = context.started_at
    context.ai_events.append(
        AIUsageEvent(
            component="test",
            operation="chat_completion",
            provider="mock",
            model="mock-chat",
            latency_ms=12.0,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            measurement_source="provider",
        )
    )
    context.retrieval_events.append(
        RetrievalUsageEvent(
            operation="document_retrieval",
            latency_ms=8.0,
            top_k=5,
            vector_hit_count=5,
            keyword_hit_count=4,
            fused_hit_count=7,
            returned_count=2,
        )
    )

    try:
        service.persist_context(context)
        details = service.get_request_details(request_id)
        assert details is not None
        assert details["request"]["request_id"] == request_id
        assert len(details["ai_events"]) == 1
        assert len(details["retrieval_events"]) == 1
        overview = service.get_overview()
        assert int(overview["total_requests"]) >= 1
        print("Usage analytics PostgreSQL integration test passed")
    except Exception as exc:
        raise RuntimeError(
            "Usage analytics integration test requires initialized PostgreSQL. "
            "Run scripts.init_sql_data only against the isolated development "
            f"database. Original error: {exc}"
        ) from exc
    finally:
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM ai_usage_events WHERE request_id = :request_id"),
                    {"request_id": request_id},
                )
                connection.execute(
                    text("DELETE FROM retrieval_events WHERE request_id = :request_id"),
                    {"request_id": request_id},
                )
                connection.execute(
                    text("DELETE FROM rag_request_runs WHERE request_id = :request_id"),
                    {"request_id": request_id},
                )
        except Exception:
            pass


if __name__ == "__main__":
    main()

