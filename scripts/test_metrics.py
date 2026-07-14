from __future__ import annotations

from app.core.metrics import (
    record_graph_execution,
    record_http_request,
    record_model_usage,
    record_node_execution,
    record_retrieval,
    record_retrieval_evaluation,
    record_document_operation,
    render_metrics,
)


def main() -> None:
    record_http_request(
        method="POST",
        route="/api/v1/graph-chat",
        status_code=200,
        latency_ms=20.0,
    )
    record_node_execution(
        node_name="retrieve",
        intent="doc_qa",
        status="success",
        latency_ms=10.0,
    )
    record_graph_execution(
        intent="doc_qa",
        status="success",
        latency_ms=25.0,
    )
    record_model_usage(
        provider="mock",
        model="mock-model",
        operation="chat_completion",
        status="success",
        latency_ms=5.0,
        input_tokens=10,
        output_tokens=5,
        measurement_source="provider",
    )
    record_retrieval(
        retrieval_mode="hybrid",
        status="success",
        latency_ms=8.0,
        degraded=False,
    )
    record_retrieval_evaluation(
        status="completed",
        metrics={"recall@5": 0.8, "mrr@5": 0.7},
        latency={
            "retrieval_total": {
                "p50_ms": 10.0,
                "p95_ms": 20.0,
                "p99_ms": 25.0,
            }
        },
    )
    record_document_operation(
        operation="document_indexed",
        status="indexed",
        latency_ms=15.0,
    )
    payload, content_type = render_metrics()
    text_payload = payload.decode("utf-8")
    assert "industrial_rag_http_requests_total" in text_payload
    assert "industrial_rag_node_executions_total" in text_payload
    assert "industrial_rag_model_calls_total" in text_payload
    assert "industrial_rag_retrieval_requests_total" in text_payload
    assert "industrial_rag_retrieval_evaluation_score" in text_payload
    assert "industrial_rag_retrieval_evaluation_latency_ms" in text_payload
    assert "industrial_rag_document_operations_total" in text_payload
    assert "text/plain" in content_type
    print("Prometheus metrics mock test passed")


if __name__ == "__main__":
    main()
