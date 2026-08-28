from __future__ import annotations

from app.core.config import settings
from app.core.logger import log_business_event, observe_node
from app.core.metrics import record_answer_validation
from app.generation import (
    LLMSemanticCitationVerifier,
    apply_semantic_support_validation,
    choose_validation_action,
    validate_answer_citations,
)
from app.graph.state import IndustrialRAGState


semantic_verifier = None


def _get_semantic_verifier():
    global semantic_verifier
    if semantic_verifier is None:
        semantic_verifier = LLMSemanticCitationVerifier()
    return semantic_verifier


@observe_node("answer_verifier")
def answer_verifier_node(state: IndustrialRAGState) -> dict:
    answer = state.get("draft_answer") or state.get("answer", "")
    validation_required = (
        state.get("intent") in {"rag", "sql"}
        and not state.get("answer_abstained", False)
    )
    validation, answer_structure = validate_answer_citations(
        answer,
        state.get("generation_contexts", []),
        citation_coverage_threshold=settings.generation_citation_coverage_threshold,
        validation_required=validation_required,
    )
    cited_claims = [
        claim
        for claim in answer_structure.get("claims", [])
        if claim.get("citation_ids")
    ]
    has_strict_claims = any(
        claim.get("evidence_policy") == "strict" for claim in cited_claims
    )
    if (
        settings.generation_semantic_validation_enabled
        and validation_required
        and cited_claims
    ):
        try:
            semantic_result = _get_semantic_verifier().verify(
                question=state.get("question", ""),
                claims=answer_structure.get("claims", []),
                contexts=state.get("generation_contexts", []),
            )
            validation, answer_structure = apply_semantic_support_validation(
                validation,
                answer_structure,
                semantic_result,
                support_threshold=settings.generation_semantic_support_threshold,
            )
        except Exception as exc:
            configured_fail_open = bool(
                settings.generation_semantic_validation_fail_open
            )
            effective_fail_open = configured_fail_open and not has_strict_claims
            semantic_reasons = list(validation.get("failure_reasons", []))
            if not effective_fail_open:
                semantic_reasons.append(
                    "strict_semantic_validation_unavailable"
                    if has_strict_claims
                    else "semantic_validation_unavailable"
                )
            validation = {
                **validation,
                "passed": not semantic_reasons,
                "failure_reasons": list(dict.fromkeys(semantic_reasons)),
                "semantic_support_checked": False,
                "semantic_validation_degraded": True,
                "semantic_validation_error": type(exc).__name__,
                "semantic_validation_fail_open_configured": configured_fail_open,
                "semantic_validation_fail_open_effective": effective_fail_open,
                "has_strict_claims": has_strict_claims,
            }
            log_business_event(
                "semantic_citation_validation_failed",
                request_id=state.get("request_id"),
                session_id=state.get("session_id"),
                status="failed",
                error_message=str(exc),
                fail_open_configured=configured_fail_open,
                fail_open_effective=effective_fail_open,
                has_strict_claims=has_strict_claims,
            )
    elif validation_required and has_strict_claims:
        semantic_reasons = list(validation.get("failure_reasons", []))
        semantic_reasons.append("strict_semantic_validation_unavailable")
        validation = {
            **validation,
            "passed": False,
            "failure_reasons": list(dict.fromkeys(semantic_reasons)),
            "semantic_support_checked": False,
            "semantic_validation_degraded": True,
            "semantic_validation_error": "disabled",
            "semantic_validation_fail_open_configured": bool(
                settings.generation_semantic_validation_fail_open
            ),
            "semantic_validation_fail_open_effective": False,
            "has_strict_claims": True,
        }
    answer_structure["missing_information"] = list(
        state.get("missing_aspects", [])
    )

    validation_history = list(state.get("answer_validation_history", []))
    initial_line_count = int(
        validation_history[0].get(
            "initial_line_count",
            validation_history[0].get("line_count", validation["line_count"]),
        )
        if validation_history
        else validation["line_count"]
    )
    current_line_count = int(validation["line_count"])
    initial_claim_count = int(
        validation_history[0].get(
            "initial_claim_count",
            validation_history[0].get("claim_count", validation["claim_count"]),
        )
        if validation_history
        else validation["claim_count"]
    )
    current_claim_count = int(validation["claim_count"])
    validation.update(
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
            "recommended_action": choose_validation_action(
                validation,
                repair_enabled=False,
                retry_count=0,
                answer_abstained=state.get("answer_abstained", False),
            ),
            "initial_claim_count": initial_claim_count,
            "current_claim_count": current_claim_count,
            "removed_claim_count": max(
                0, initial_claim_count - current_claim_count
            ),
            "claim_retention_rate": round(
                min(1.0, current_claim_count / initial_claim_count),
                4,
            )
            if initial_claim_count
            else 1.0,
        }
    )
    record_answer_validation(
        intent=state.get("intent"),
        passed=bool(validation["passed"]),
        citation_coverage=float(validation["citation_coverage"]),
    )
    log_business_event(
        "answer_validation_completed",
        request_id=state.get("request_id"),
        session_id=state.get("session_id"),
        status="passed" if validation["passed"] else "rejected",
        validation_mode=validation["citation_validation_mode"],
        citation_coverage=validation["citation_coverage"],
        line_count=validation["line_count"],
        cited_line_count=validation["cited_line_count"],
        uncited_line_count=validation["uncited_line_count"],
        invalid_line_count=validation["invalid_line_count"],
        semantic_support_checked=validation.get("semantic_support_checked", False),
        semantic_support_rate=validation.get("semantic_support_rate"),
        semantic_validation_degraded=validation.get(
            "semantic_validation_degraded", False
        ),
        has_strict_claims=has_strict_claims,
        initial_line_count=validation["initial_line_count"],
        current_line_count=validation["current_line_count"],
        removed_line_count=validation["removed_line_count"],
        line_retention_rate=validation["line_retention_rate"],
        recommended_action=validation["recommended_action"],
        generation_retry_count=0,
    )
    return {
        "answer_validation": validation,
        "answer_validation_history": [dict(validation)],
        "answer_structure": answer_structure,
        "generation_quality_passed": bool(validation["passed"]),
    }


def route_after_answer_verifier(state: IndustrialRAGState) -> str:
    del state
    return "finalize"
