from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


DEFAULT_EVIDENCE_THRESHOLDS = (0.45, 0.50, 0.55, 0.60)


def classify_generation_result(item: dict[str, Any]) -> dict[str, Any]:
    """Assign one primary failure category and reusable diagnostic tags."""
    tags: list[str] = []
    answerable = bool(item.get("answerable", True))
    abstained = bool(item.get("answer_abstained", False))
    refusal_text = " ".join(
        str(item.get(field) or "")
        for field in ("abstain_reason", "answer", "answer_preview")
    )

    checks = (
        ("intent_ok", "intent_mismatch"),
        ("doc_type_ok", "document_type_miss"),
        ("source_ok", "source_miss"),
        ("answer_keywords_ok", "answer_content_gap"),
        ("citation_contract_ok", "citation_contract_failure"),
        ("semantic_support_ok", "semantic_support_failure"),
        ("abstention_ok", "abstention_error"),
        ("memory_followup_ok", "memory_followup_failure"),
        ("forbidden_claims_ok", "forbidden_claim"),
    )
    for field, tag in checks:
        if field == "answer_keywords_ok" and not answerable:
            continue
        value = item.get(field)
        if value is not None and not bool(value):
            tags.append(tag)

    evidence_enough = item.get("evidence_enough")
    if answerable and abstained:
        tags.append("false_refusal")
        if evidence_enough is False or any(
            marker in refusal_text
            for marker in ("证据可信度不足", "未检索到足够", "缺少以下关键维度")
        ):
            primary = "evidence_rejection"
        elif not bool(item.get("citation_contract_ok", True)):
            primary = "citation_rejection"
        else:
            primary = "unexpected_refusal"
    elif not answerable and not abstained:
        tags.append("unsafe_non_refusal")
        primary = "unsafe_non_refusal"
    elif not bool(item.get("intent_ok", True)):
        primary = "intent_routing"
    elif not bool(item.get("source_ok", True)):
        primary = "retrieval_source"
    elif not bool(item.get("doc_type_ok", True)):
        primary = "retrieval_document_type"
    elif not bool(item.get("citation_contract_ok", True)):
        primary = "citation_rejection"
    elif not bool(item.get("semantic_support_ok", True)):
        primary = "semantic_citation_rejection"
    elif answerable and not bool(item.get("answer_keywords_ok", True)):
        primary = "answer_content"
    elif item.get("memory_followup_ok") is False:
        primary = "memory_followup"
    elif not bool(item.get("all_ok", True)):
        primary = "other"
    else:
        primary = "passed"

    return {
        "failure_category": primary,
        "failure_tags": list(dict.fromkeys(tags)),
    }


def build_evidence_threshold_sweep(
    results: Iterable[dict[str, Any]],
    thresholds: Iterable[float] = DEFAULT_EVIDENCE_THRESHOLDS,
) -> list[dict[str, Any]]:
    """Evaluate threshold decisions against answerable/knowledge-gap labels.

    This is a calibration aid, not an automatic production configuration
    update. Items without an observed evidence confidence are excluded.
    """
    observations = [
        item
        for item in results
        if item.get("evidence_confidence") is not None
        and item.get("intent_ok") is not False
    ]
    if not observations:
        return []
    sweep: list[dict[str, Any]] = []
    for raw_threshold in thresholds:
        threshold = float(raw_threshold)
        correct = false_refusals = unsafe_answers = 0
        answerable_count = sum(
            1 for item in observations if item.get("answerable", True)
        )
        knowledge_gap_count = len(observations) - answerable_count
        for item in observations:
            confidence = float(item.get("evidence_confidence") or 0.0)
            missing_aspects = item.get("missing_aspects") or []
            predicted_answerable = confidence >= threshold and not missing_aspects
            expected_answerable = bool(item.get("answerable", True))
            correct += int(predicted_answerable == expected_answerable)
            false_refusals += int(expected_answerable and not predicted_answerable)
            unsafe_answers += int(not expected_answerable and predicted_answerable)
        total = len(observations)
        sweep.append(
            {
                "threshold": threshold,
                "sample_count": total,
                "decision_accuracy": round(correct / total, 4) if total else 0.0,
                "false_refusal_rate": (
                    round(false_refusals / answerable_count, 4)
                    if answerable_count
                    else 0.0
                ),
                "unsafe_answer_rate": (
                    round(unsafe_answers / knowledge_gap_count, 4)
                    if knowledge_gap_count
                    else 0.0
                ),
            }
        )
    return sweep


def analyze_generation_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    classified = [
        {**item, **classify_generation_result(item)} for item in results
    ]
    failure_categories = Counter(
        item["failure_category"]
        for item in classified
        if item["failure_category"] != "passed"
    )
    failure_tags = Counter(
        tag for item in classified for tag in item["failure_tags"]
    )
    answerable = [item for item in classified if item.get("answerable", True)]
    knowledge_gaps = [
        item for item in classified if not item.get("answerable", True)
    ]
    false_refusals = sum(
        1 for item in answerable if item.get("answer_abstained", False)
    )
    correct_gap_refusals = sum(
        1 for item in knowledge_gaps if item.get("answer_abstained", False)
    )
    return {
        "failed_count": sum(1 for item in classified if not item.get("all_ok")),
        "passed_count": sum(1 for item in classified if item.get("all_ok")),
        "failure_categories": dict(failure_categories),
        "failure_tags": dict(failure_tags),
        "answerable_count": len(answerable),
        "false_refusal_count": false_refusals,
        "false_refusal_rate": (
            round(false_refusals / len(answerable), 4) if answerable else 0.0
        ),
        "knowledge_gap_count": len(knowledge_gaps),
        "knowledge_gap_refusal_accuracy": (
            round(correct_gap_refusals / len(knowledge_gaps), 4)
            if knowledge_gaps
            else 0.0
        ),
        "evidence_threshold_sweep": build_evidence_threshold_sweep(classified),
    }
