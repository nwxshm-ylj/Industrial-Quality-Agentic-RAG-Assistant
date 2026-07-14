from __future__ import annotations

import json
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from app.evaluation.retrieval_evaluator import RetrievalEvaluator
from app.evaluation.retrieval_metrics import (
    calculate_rank_metrics,
    summarize_latency,
)
from app.rag.embeddings.mock_provider import MockEmbeddingProvider


class MockRetriever:
    def __init__(self) -> None:
        self.embedding_provider = MockEmbeddingProvider(dimension=8)

    def retrieve_with_metadata(self, question: str, top_k: int = 5) -> dict:
        # Exercise the query/document boundary without any paid API call.
        assert len(self.embedding_provider.embed_query(question)) == 8
        if question == "force failure":
            raise RuntimeError("expected mock failure")
        contexts = [
            {
                "doc_id": "doc-noise",
                "chunk_id": "noise-1",
                "source": "noise.md",
                "score": 0.9,
                "retrieval_source": "keyword",
            },
            {
                "doc_id": "doc-target",
                "chunk_id": "target-1",
                "source": "target.md",
                "score": 0.8,
                "retrieval_source": "keyword+vector",
            },
            {
                "doc_id": "doc-target",
                "chunk_id": "target-2",
                "source": "target.md",
                "score": 0.7,
                "retrieval_source": "vector",
            },
        ][:top_k]
        return {
            "contexts": contexts,
            "metadata": {
                "retrieval_mode": "hybrid",
                "degraded": False,
                "qdrant_latency_ms": 8.0,
                "opensearch_latency_ms": 5.0,
                "fusion_latency_ms": 1.0,
                "reranker_latency_ms": 0.0,
            },
        }


def test_rank_metrics() -> None:
    results = [
        {"doc_id": "noise"},
        {"doc_id": "relevant-a"},
        {"doc_id": "relevant-b"},
    ]
    metrics = calculate_rank_metrics(
        results,
        relevant_ids=["relevant-a", "relevant-b"],
        relevance_field="doc_id",
        k_values=[1, 3],
        top_k=3,
    )
    assert metrics["recall@1"] == 0.0
    assert metrics["hit_rate@1"] == 0.0
    assert metrics["recall@3"] == 1.0
    assert metrics["hit_rate@3"] == 1.0
    assert metrics["mrr@3"] == 0.5
    assert isclose(metrics["precision@3"], 2 / 3, rel_tol=1e-5)
    assert 0.0 < metrics["ndcg@3"] < 1.0


def test_source_deduplication() -> None:
    results = [
        {"source": "folder/target.md", "chunk_id": "one"},
        {"source": "folder/target.md", "chunk_id": "two"},
        {"source": "other.md", "chunk_id": "three"},
    ]
    metrics = calculate_rank_metrics(
        results,
        relevant_ids=["target.md"],
        relevance_field="source",
        k_values=[1, 3],
        top_k=3,
    )
    assert metrics["recall@1"] == 1.0
    assert metrics["mrr@3"] == 1.0
    assert metrics["precision@3"] == round(1 / 3, 6)


def test_latency_summary() -> None:
    summary = summarize_latency([10, 20, 30, 40, 50])
    assert summary["count"] == 5
    assert summary["avg_ms"] == 30.0
    assert summary["p50_ms"] == 30.0
    assert summary["p95_ms"] == 48.0
    assert summary["p99_ms"] == 49.6


def test_evaluator_with_mock_retriever() -> None:
    evaluator = RetrievalEvaluator(MockRetriever())
    report = evaluator.run(
        [
            {
                "id": "mock-success",
                "question": "find target",
                "relevance_field": "source",
                "relevant_ids": ["target.md"],
            },
            {
                "id": "mock-failure",
                "question": "force failure",
                "relevance_field": "source",
                "relevant_ids": ["target.md"],
            },
        ],
        top_k=3,
        k_values=[1, 3],
        run_id="mock-run",
        dataset_name="mock-dataset",
    )
    assert report["status"] == "partial"
    assert report["summary"]["total_questions"] == 2
    assert report["summary"]["successful_questions"] == 1
    assert report["summary"]["failed_questions"] == 1
    assert report["metrics"]["mrr@3"] == 0.25
    assert report["metrics"]["recall@3"] == 0.5
    assert report["latency"]["retrieval_total"]["count"] == 2
    assert report["items"][0]["ranked_results"][1]["relevant"] is True
    assert "text" not in report["items"][0]["ranked_results"][1]

    with TemporaryDirectory() as temporary_directory:
        report_path = Path(temporary_directory) / "latest.json"
        evaluator.write_report(report, report_path)
        evaluator.write_report(report, report_path)
        persisted = json.loads(report_path.read_text(encoding="utf-8"))
        assert persisted["run_id"] == "mock-run"
        assert not list(report_path.parent.glob("*.tmp"))


def main() -> None:
    test_rank_metrics()
    test_source_deduplication()
    test_latency_summary()
    test_evaluator_with_mock_retriever()
    print("Retrieval evaluation metrics and mock evaluator tests passed")


if __name__ == "__main__":
    main()
