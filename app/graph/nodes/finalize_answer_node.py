from __future__ import annotations

from app.core.config import settings
from app.core.logger import log_business_event, observe_node
from app.generation import (
    build_citation_safe_answer,
    is_abstention_answer,
    validate_answer_citations,
)
from app.graph.state import IndustrialRAGState
from app.streaming.events import emit_answer_replace


def _validation_refusal(state: IndustrialRAGState) -> str:
    validation = state.get("answer_validation", {})
    reasons = validation.get("failure_reasons", [])
    reason_text = "、".join(str(item) for item in reasons) or "引用校验未通过"
    return (
        "当前回答未通过引用一致性校验，因此未向你返回未经验证的结论。"
        f"校验原因：{reason_text}。请补充更明确的问题或相关资料后重试。"
    )


@observe_node("finalize_answer")
def finalize_answer_node(state: IndustrialRAGState) -> dict:
    citation_pruned = False
    validation = state.get("answer_validation", {})
    answer_structure = state.get("answer_structure", {})
    if state.get("generation_quality_passed", False):
        answer = state.get("draft_answer") or state.get("answer", "")
        abstained = state.get("answer_abstained", False)
    else:
        failure_reasons = set(validation.get("failure_reasons", []))
        safe_answer = ""
        prunable_reasons = {
            "citation_coverage_below_threshold",
            "semantic_unsupported_claims",
            "semantic_support_below_threshold",
        }
        if failure_reasons and failure_reasons.issubset(prunable_reasons):
            candidate = build_citation_safe_answer(answer_structure)
            if candidate:
                candidate_validation, candidate_structure = validate_answer_citations(
                    candidate,
                    state.get("generation_contexts", []),
                    citation_coverage_threshold=(
                        settings.generation_citation_coverage_threshold
                    ),
                    validation_required=True,
                )
                if candidate_validation.get("passed"):
                    # The candidate is built only from claims whose
                    # claim_type is still ``supported``. Preserve a successful
                    # semantic check even when pruning was triggered solely by
                    # deterministic citation coverage (for example, uncited
                    # section headings in an otherwise supported answer).
                    semantic_pruning = bool(
                        validation.get("semantic_support_checked", False)
                    )
                    if semantic_pruning:
                        retained_claim_count = len(
                            candidate_structure.get("claims", [])
                        )
                        candidate_validation.update(
                            {
                                "semantic_support_checked": True,
                                "semantic_support_rate": 1.0,
                                "semantic_support_threshold": settings.generation_semantic_support_threshold,
                                "semantic_checked_claim_count": retained_claim_count,
                                "semantic_supported_claim_count": retained_claim_count,
                                "semantic_partial_claim_count": 0,
                                "semantic_unsupported_claim_count": 0,
                                "semantic_validation_degraded": False,
                                "semantic_validation_error": None,
                            }
                        )
                    safe_answer = candidate
                    validation = {
                        **candidate_validation,
                        "repair_attempted": (
                            state.get("generation_retry_count", 0) > 0
                        ),
                        "deterministic_pruning_applied": True,
                        "semantic_pruning_applied": semantic_pruning,
                        "recommended_action": "finalize",
                    }
                    answer_structure = candidate_structure
        if safe_answer:
            answer = safe_answer
            abstained = False
            citation_pruned = True
            log_business_event(
                "answer_citation_pruned",
                request_id=state.get("request_id"),
                session_id=state.get("session_id"),
                status="success",
                citation_coverage=validation.get("citation_coverage"),
            )
        else:
            answer = _validation_refusal(state)
            abstained = True

    semantic_abstention = is_abstention_answer(answer)
    abstained = bool(abstained or semantic_abstention)
    emit_answer_replace(answer)
    result: dict = {
        "answer": answer,
        "answer_abstained": abstained,
        "citation_pruned": citation_pruned,
        "answer_validation": validation,
        "answer_structure": answer_structure,
        "generation_quality_passed": bool(
            state.get("generation_quality_passed", False) or citation_pruned
        ),
    }
    if semantic_abstention and not state.get("abstain_reason"):
        result["abstain_reason"] = "生成答案确认当前知识库未提供所需事实"
    if not result["generation_quality_passed"]:
        result["answer_structure"] = {
            "summary": answer,
            "claims": [],
            "missing_information": list(state.get("missing_aspects", [])),
            "supplementary_advice": [],
        }
    return result
