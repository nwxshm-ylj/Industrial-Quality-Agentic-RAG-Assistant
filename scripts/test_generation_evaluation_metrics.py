from scripts.evaluate_system import calculate_metrics, check_doc_type, evaluate_one


def _invoke_factory(result: dict):
    def invoke(*, question: str, top_k: int, session_id: str):
        assert question
        assert top_k == 3
        assert session_id.startswith("evaluation-")
        return result

    return invoke


def main() -> None:
    assert check_doc_type(
        {"citations": [{"doc_type": "LESSON_LEARNED"}]},
        "LessonLearn",
    )
    assert check_doc_type(
        {"citations": [{"doc_type": "STANDARD_WORK_DOCUMENT"}]},
        "标准作业文档",
    )
    cited = evaluate_one(
        {
            "id": "GEN-MOCK-1",
            "category": "standard_qa",
            "question": "标准要求是什么？",
            "expected_intent": "rag",
            "expected_source_contains": "standard.pdf",
            "expected_answer_keywords": ["扭矩"],
            "answerable": True,
        },
        invoke_fn=_invoke_factory(
            {
                "intent": "rag",
                "answer": "标准要求检查扭矩【资料1】。",
                "citations": [{"source": "standard.pdf"}],
                "answer_abstained": False,
                "answer_validation": {
                    "passed": True,
                    "citation_contract_passed": True,
                    "citation_coverage": 1.0,
                    "semantic_support_checked": True,
                    "semantic_support_rate": 1.0,
                },
                "generation_quality_passed": True,
                "generation_retry_count": 0,
            }
        ),
    )
    repaired = evaluate_one(
        {
            "id": "GEN-MOCK-2",
            "question": "异常如何排查？",
            "expected_intent": "rag",
            "expected_answer_keywords": ["相机"],
            "answerable": True,
        },
        invoke_fn=_invoke_factory(
            {
                "intent": "rag",
                "answer": "优先检查相机【资料1】。",
                "citations": [],
                "answer_abstained": False,
                "answer_validation": {
                    "passed": True,
                    "citation_contract_passed": True,
                    "citation_coverage": 1.0,
                    "semantic_support_checked": True,
                    "semantic_support_rate": 1.0,
                },
                "generation_quality_passed": True,
                "generation_retry_count": 1,
            }
        ),
    )
    abstained = evaluate_one(
        {
            "id": "GEN-MOCK-3",
            "question": "未收录车型参数是什么？",
            "expected_intent": "rag",
            "expected_answer_keywords": ["无法确认"],
            "answerable": False,
        },
        invoke_fn=_invoke_factory(
            {
                "intent": "rag",
                "answer": "当前知识库无法确认该参数。",
                "citations": [],
                "answer_abstained": True,
                "answer_validation": {
                    "passed": True,
                    "citation_coverage": 1.0,
                },
                "generation_quality_passed": True,
                "generation_retry_count": 0,
            }
        ),
    )

    metrics = calculate_metrics([cited, repaired, abstained])
    assert metrics["citation_validation_pass_rate"] == 1.0
    assert metrics["avg_citation_coverage"] == 1.0
    assert metrics["semantic_validation_coverage_rate"] == 1.0
    assert metrics["semantic_support_pass_rate"] == 1.0
    assert metrics["repair_trigger_rate"] == 0.3333
    assert metrics["llm_repair_selection_rate"] == 0.3333
    assert metrics["deterministic_prune_selection_rate"] == 0.0
    assert metrics["direct_finalize_selection_rate"] == 0.6667
    assert metrics["repair_avoidance_rate"] == 0.0
    assert metrics["avg_latency_llm_repair_ms"] >= 0.0
    assert metrics["avg_latency_without_llm_repair_ms"] >= 0.0
    assert metrics["repair_success_rate"] == 1.0
    assert metrics["final_refusal_rate"] == 0.3333
    assert metrics["abstention_accuracy"] == 1.0
    assert metrics["p95_latency_ms"] >= 0.0
    print("Generation evaluation metrics test passed")


if __name__ == "__main__":
    main()
