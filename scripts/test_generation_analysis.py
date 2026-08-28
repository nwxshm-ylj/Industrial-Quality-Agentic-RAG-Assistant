from app.evaluation.generation_analysis import analyze_generation_results


def main() -> None:
    results = [
        {
            "id": "A1",
            "all_ok": False,
            "answerable": True,
            "answer_abstained": True,
            "abstention_ok": False,
            "evidence_enough": False,
            "evidence_confidence": 0.52,
            "missing_aspects": [],
            "intent_ok": True,
            "doc_type_ok": True,
            "source_ok": True,
            "answer_keywords_ok": False,
            "citation_contract_ok": True,
            "forbidden_claims_ok": True,
        },
        {
            "id": "G1",
            "all_ok": True,
            "answerable": False,
            "answer_abstained": True,
            "abstention_ok": True,
            "evidence_enough": False,
            "evidence_confidence": 0.30,
            "missing_aspects": [],
            "intent_ok": True,
            "doc_type_ok": True,
            "source_ok": True,
            "answer_keywords_ok": True,
            "citation_contract_ok": True,
            "forbidden_claims_ok": True,
        },
    ]
    analysis = analyze_generation_results(results)
    assert analysis["failed_count"] == 1
    assert analysis["failure_categories"]["evidence_rejection"] == 1
    assert analysis["false_refusal_rate"] == 1.0
    assert analysis["knowledge_gap_refusal_accuracy"] == 1.0

    sweep = {item["threshold"]: item for item in analysis["evidence_threshold_sweep"]}
    assert sweep[0.5]["decision_accuracy"] == 1.0
    assert sweep[0.55]["false_refusal_rate"] == 1.0
    print("Generation failure analysis test passed")


if __name__ == "__main__":
    main()
