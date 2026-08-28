from __future__ import annotations

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
    reason_text = "、".join(str(item) for item in reasons) or "引用编号校验未通过"
    return (
        "当前回答没有保留下来可验证的资料引用，因此未返回未标注来源的内容。"
        f"校验原因：{reason_text}。请补充更明确的问题或相关资料后重试。"
    )


@observe_node("finalize_answer")
def finalize_answer_node(state: IndustrialRAGState) -> dict:
    citation_pruned = False
    validation = dict(state.get("answer_validation", {}))
    answer_structure = dict(state.get("answer_structure", {}))
    original_semantic_checked = bool(
        validation.get("semantic_support_checked", False)
    )
    if state.get("generation_quality_passed", False):
        answer = state.get("draft_answer") or state.get("answer", "")
        abstained = state.get("answer_abstained", False)
    else:
        failure_reasons = set(validation.get("failure_reasons", []))
        prunable_reasons = {
            "invalid_citation_ids",
            "uncited_answer_lines",
            "no_valid_citations",
            "semantic_partial_claims",
            "semantic_unsupported_claims",
            "semantic_support_below_threshold",
        }
        candidate = (
            build_citation_safe_answer(answer_structure)
            if failure_reasons and failure_reasons.issubset(prunable_reasons)
            else ""
        )
        safe_answer = ""
        if candidate:
            candidate_validation, candidate_structure = validate_answer_citations(
                candidate,
                state.get("generation_contexts", []),
                validation_required=True,
            )
            if candidate_validation.get("passed"):
                semantic_pruning_applied = bool(
                    failure_reasons
                    & {
                        "semantic_partial_claims",
                        "semantic_unsupported_claims",
                        "semantic_support_below_threshold",
                    }
                )
                initial_line_count = int(
                    validation.get(
                        "initial_line_count",
                        validation.get("line_count", 0),
                    )
                )
                current_line_count = int(
                    candidate_validation.get("line_count", 0)
                )
                initial_claim_count = int(
                    validation.get(
                        "initial_claim_count",
                        validation.get("claim_count", 0),
                    )
                )
                current_claim_count = int(
                    candidate_validation.get("claim_count", 0)
                )
                candidate_validation.update(
                    {
                        "initial_line_count": initial_line_count,
                        "current_line_count": current_line_count,
                        "removed_line_count": max(
                            0, initial_line_count - current_line_count
                        ),
                        "line_retention_rate": round(
                            min(1.0, current_line_count / initial_line_count),
                            4,
                        )
                        if initial_line_count
                        else 1.0,
                        "repair_attempted": False,
                        "deterministic_pruning_applied": True,
                        "semantic_pruning_applied": semantic_pruning_applied,
                        "recommended_action": "finalize",
                        "initial_claim_count": initial_claim_count,
                        "current_claim_count": current_claim_count,
                        "removed_claim_count": max(
                            0, initial_claim_count - current_claim_count
                        ),
                        "claim_retention_rate": round(
                            min(
                                1.0,
                                current_claim_count / initial_claim_count,
                            ),
                            4,
                        )
                        if initial_claim_count
                        else 1.0,
                        "semantic_support_checked": (
                            original_semantic_checked
                            if semantic_pruning_applied
                            else candidate_validation.get(
                                "semantic_support_checked", False
                            )
                        ),
                        "semantic_support_rate": (
                            1.0 if semantic_pruning_applied else None
                        ),
                        "semantic_checked_claim_count": (
                            current_claim_count
                            if semantic_pruning_applied
                            else 0
                        ),
                        "semantic_supported_claim_count": (
                            current_claim_count
                            if semantic_pruning_applied
                            else 0
                        ),
                        "semantic_partial_claim_count": 0,
                        "semantic_unsupported_claim_count": 0,
                    }
                )
                safe_answer = candidate
                validation = candidate_validation
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
                validation_mode=validation.get("citation_validation_mode"),
                citation_coverage=validation.get("citation_coverage"),
                initial_line_count=validation.get("initial_line_count"),
                final_line_count=validation.get("current_line_count"),
                removed_line_count=validation.get("removed_line_count"),
                line_retention_rate=validation.get("line_retention_rate"),
            )
        else:
            answer = _validation_refusal(state)
            abstained = True

    validation.update(
        {
            "final_line_count": int(
                validation.get(
                    "current_line_count", validation.get("line_count", 0)
                )
            ),
            "final_line_retention_rate": validation.get(
                "line_retention_rate", 1.0
            ),
            "final_claim_count": int(
                validation.get(
                    "current_claim_count", validation.get("claim_count", 0)
                )
            ),
            "final_claim_retention_rate": validation.get(
                "claim_retention_rate", 1.0
            ),
            "repair_attempted": False,
            "semantic_support_checked": validation.get(
                "semantic_support_checked", False
            ),
            "semantic_support_rate": validation.get("semantic_support_rate"),
        }
    )
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
            "lines": [],
            "missing_information": list(state.get("missing_aspects", [])),
            "supplementary_advice": [],
        }
    return result
