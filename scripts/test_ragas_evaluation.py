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
                "question": "轮毂识别异常如何排查？",
                "reference_answer": "检查曝光、光源和PR配置。",
            },
            {
                "id": "mock-2",
                "question": "OCR失败如何排查？",
                "reference_answer": "检查打印质量、坐标和OCR模板。",
            },
        ],
        result_provider=lambda question: {
            "answer": f"针对{question}，请根据标准流程检查。",
            "contexts": [
                {"text": "标准要求检查曝光、光源、打印质量和模板。"}
            ],
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
    print("RAGAS semantic evaluation adapter tests passed without paid APIs")


if __name__ == "__main__":
    main()
