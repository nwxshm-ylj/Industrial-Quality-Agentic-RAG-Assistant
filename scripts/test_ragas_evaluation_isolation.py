from __future__ import annotations

from tempfile import TemporaryDirectory

from app.evaluation.ragas_evaluator import SemanticEvaluationSample
from app.graph.nodes.load_memory_node import load_memory_node
from app.graph.nodes.save_memory_node import save_memory_node
from app.services.ragas_evaluation_service import RagasEvaluationService


class _MetricSuite:
    suite_name = "mock-ragas"
    suite_version = "test"
    judge_model = "mock-judge"

    def score(self, sample: SemanticEvaluationSample) -> dict[str, float]:
        assert sample.retrieved_contexts
        return {
            "context_precision": 1.0,
            "context_recall": 1.0,
            "response_relevancy": 1.0,
            "faithfulness": 1.0,
        }


class _GraphChain:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def invoke(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {
            "answer": "mock grounded answer",
            "contexts": [
                {
                    "doc_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "source": "mock.pdf",
                    "text": "mock grounded evidence",
                }
            ],
            "citations": [{"doc_id": "doc-1", "chunk_id": "chunk-1"}],
            "intent": "doc_qa",
            "rewritten_query": kwargs["question"],
            "evidence_score": 1.0,
            "evidence_enough": True,
            "metadata": {"retrieval_mode": "mock"},
        }


class _AuditService:
    def log_action(self, **kwargs) -> None:
        del kwargs


def main() -> None:
    disabled_state = {
        "memory_enabled": False,
        "session_id": "evaluation-test",
        "question": "question",
        "answer": "answer",
    }
    loaded = load_memory_node(disabled_state)  # type: ignore[arg-type]
    assert loaded["memory_messages"] == []
    assert loaded["memory_metadata"]["memory_mode"] == "disabled_for_evaluation"
    assert save_memory_node(disabled_state) == {}  # type: ignore[arg-type]

    graph_chain = _GraphChain()
    with TemporaryDirectory() as report_dir:
        report = RagasEvaluationService(
            metric_suite=_MetricSuite(),
            graph_chain=graph_chain,  # type: ignore[arg-type]
            report_dir=report_dir,
            audit_service=_AuditService(),  # type: ignore[arg-type]
        ).run_evaluation(
            username="admin",
            role="admin",
            request_id="isolation-test",
            max_questions=2,
        )

    assert report["status"] == "completed"
    assert len(graph_chain.calls) == 2
    assert all(call["memory_enabled"] is False for call in graph_chain.calls)
    session_ids = {call["session_id"] for call in graph_chain.calls}
    assert len(session_ids) == 2
    assert all(session_id.startswith("evaluation-") for session_id in session_ids)
    assert report["items"][0]["retrieved_contexts"][0]["chunk_id"] == "chunk-1"
    print("RAGAS evaluation isolation tests passed without external APIs")


if __name__ == "__main__":
    main()
