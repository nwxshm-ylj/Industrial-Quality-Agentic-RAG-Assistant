from app.evaluation.ragas_evaluator import (
    RAGAS_METRIC_NAMES,
    SemanticEvaluationSample,
    SemanticRAGEvaluator,
)


class _MockMetricSuite:
    suite_name = "mock-ragas"
    suite_version = "test"
    judge_model = "mock-judge"

    def score(
        self,
        sample: SemanticEvaluationSample,
    ) -> dict[str, float]:
        assert sample.user_input
        assert sample.retrieved_contexts
        assert sample.response
        assert sample.reference
        return {
            "context_precision": 0.9,
            "context_recall": 0.8,
            "response_relevancy": 0.85,
            "faithfulness": 0.95,
        }


def main() -> None:
    evaluator = SemanticRAGEvaluator(_MockMetricSuite())
    report = evaluator.run(
        [
            {
                "id": "mock-1",
                "question": "如何检查设备异常？",
                "reference_answer": "根据设备手册执行点检。",
                "expected_doc_ids": ["doc-1"],
                "expected_chunk_ids": ["chunk-1"],
                "reference_contexts": ["设备手册要求执行点检。"],
            },
            {
                "id": "mock-2",
                "question": "如何处理质量报警？",
                "reference_answer": "根据质量标准执行排查。",
            },
        ],
        result_provider=lambda question: {
            "answer": f"针对{question}，请根据标准流程检查。",
            "contexts": [
                {
                    "doc_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "source": "mock.pdf",
                    "text": "标准要求检查设备状态并保留记录。",
                }
            ],
            "citations": [{"doc_id": "doc-1", "chunk_id": "chunk-1"}],
            "intent": "rag",
            "rewritten_query": question,
            "evidence_score": 0.9,
            "evidence_enough": True,
            "metadata": {"retrieval_mode": "mock"},
        },
        run_id="ragas_mock",
        dataset_name="mock.json",
    )

    assert report["status"] == "completed"
    assert report["framework"] == "mock-ragas"
    assert report["summary"]["total_questions"] == 2
    assert set(report["metrics"]) == set(RAGAS_METRIC_NAMES)
    assert report["metrics"]["faithfulness"] == 0.95
    assert all(item["status"] == "success" for item in report["items"])
    first_item = report["items"][0]
    assert first_item["retrieved_contexts"][0]["doc_id"] == "doc-1"
    assert first_item["expected_doc_ids"] == ["doc-1"]
    assert first_item["intent"] == "rag"
    assert first_item["evidence_enough"] is True
    print("RAGAS semantic evaluation adapter tests passed without paid APIs")


if __name__ == "__main__":
    main()
