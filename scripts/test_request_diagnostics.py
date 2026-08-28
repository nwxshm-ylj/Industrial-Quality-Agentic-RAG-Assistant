from app.observability.request_diagnostics import (
    build_diagnostic_snapshot,
    build_diagnostics_response,
    summarize_retrieval_candidates,
)
from app.core.telemetry_context import (
    get_request_context,
    reset_request_context,
    start_request_context,
)
from app.streaming.events import emit_node_progress


def main() -> None:
    source_context = {
        "doc_id": "doc-1",
        "source": "quality-case.xlsx",
        "chunk_id": "chunk-2",
        "chunk_index": 2,
        "text": "措施：更换冲头和凹模套",
        "score": 0.92,
        "evidence_bundle_id": "case-doc-1",
        "evidence_chunk_ids": ["chunk-1", "chunk-2"],
        "evidence_chunk_count": 2,
    }
    result = {
        "intent": "rag",
        "requested_retrieval_mode": "case_trace",
        "query_features": {"task_mode": "case_search"},
        "retrieval_metadata": {
            "retrieval_mode": "hybrid",
            "degraded": False,
            "fusion_strategy": "rrf",
        },
        "retrieval_diagnostics": {
            "query_hash": "hash-1",
            "vector": summarize_retrieval_candidates([source_context]),
            "final": summarize_retrieval_candidates([source_context]),
        },
        "contexts": [source_context],
        "generation_contexts": [source_context],
        "generation_context_metadata": {
            "input_context_count": 1,
            "generation_context_count": 1,
        },
        "citations": [{
            "doc_id": "doc-1",
            "chunk_id": "chunk-2",
            "evidence_chunk_ids": ["chunk-1", "chunk-2"],
            "evidence_chunk_count": 2,
        }],
        "answer": "资料中措施栏为空。",
        "evidence_enough": True,
        "generation_quality_passed": True,
        "answer_validation": {"valid": True},
    }

    private_snapshot = build_diagnostic_snapshot(
        result,
        capture_content=False,
    )
    assert private_snapshot["generation"]["answer_excerpt"] is None
    assert private_snapshot["generation"]["contexts"][0]["text_excerpt"] is None
    assert private_snapshot["retrieval"]["candidates"]["vector"][0][
        "chunk_id"
    ] == "chunk-2"

    content_snapshot = build_diagnostic_snapshot(
        result,
        capture_content=True,
    )
    assert any(
        item["code"] == "possible_empty_field_conflict"
        for item in content_snapshot["checks"]
    )
    response = build_diagnostics_response({
        "request": {
            "request_id": "request-1",
            "metadata": {"diagnostic_snapshot": content_snapshot},
        },
        "ai_events": [],
        "retrieval_events": [],
    })
    assert response["snapshot_available"] is True
    assert response["request_id"] == "request-1"

    legacy = build_diagnostics_response({
        "request": {"request_id": "legacy", "metadata": {}},
        "ai_events": [],
        "retrieval_events": [],
    })
    assert legacy["snapshot_available"] is False
    assert legacy["limitations"]

    token = start_request_context("workflow-request")
    try:
        emit_node_progress(
            node_name="retrieve",
            status="completed",
            state={"intent": "rag", "retry_count": 0},
            latency_ms=12.5,
        )
        usage_context = get_request_context()
        assert usage_context is not None
        assert usage_context.workflow_events[0]["node_name"] == "retrieve"
    finally:
        reset_request_context(token)
    print("Request diagnostics tests passed")


if __name__ == "__main__":
    main()
