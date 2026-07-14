from __future__ import annotations

from app.core.telemetry_context import (
    add_ai_usage_event,
    add_retrieval_usage_event,
    complete_request_context,
    get_request_context,
    reset_request_context,
    start_request_context,
    update_request_context,
)
from app.observability.usage_models import AIUsageEvent, RetrievalUsageEvent
from app.core.sensitive_filter import sanitize_telemetry_value


def main() -> None:
    sanitized = sanitize_telemetry_value(
        {
            "authorization": "Bearer secret-token",
            "database_url": "postgresql://user:secret@localhost/db",
            "safe": "visible",
        }
    )
    assert sanitized["authorization"] == "[REDACTED]"
    assert "secret@" not in sanitized["database_url"]
    assert sanitized["safe"] == "visible"

    token = start_request_context(
        "test-request-001",
        route="/api/v1/graph-chat",
        method="POST",
    )
    try:
        update_request_context(
            session_id="test-session",
            username="tester",
            intent="doc_qa",
        )
        add_ai_usage_event(
            AIUsageEvent(
                component="answer_generator",
                operation="chat_completion",
                provider="mock",
                model="mock-chat",
                latency_ms=12.5,
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                measurement_source="provider",
            )
        )
        add_ai_usage_event(
            AIUsageEvent(
                component="embedding_provider",
                operation="embedding_query",
                provider="mock",
                model="mock-embedding",
                latency_ms=3.0,
                input_tokens=5,
                total_tokens=5,
                measurement_source="provider",
            )
        )
        add_retrieval_usage_event(
            RetrievalUsageEvent(
                operation="document_retrieval",
                latency_ms=8.0,
                top_k=5,
                vector_hit_count=10,
                keyword_hit_count=8,
                fused_hit_count=12,
                returned_count=5,
            )
        )
        context = complete_request_context(
            status="success",
            http_status=200,
            total_latency_ms=25.0,
        )
        assert context is not None
        assert context.request_id == "test-request-001"
        assert context.input_tokens == 25
        assert context.output_tokens == 10
        assert context.total_tokens == 35
        assert context.embedding_tokens == 5
        assert len(context.retrieval_events) == 1
        assert context.completed_at is not None
        print("Telemetry context mock test passed")
    finally:
        reset_request_context(token)

    assert get_request_context() is None


if __name__ == "__main__":
    main()
