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


semantic_verifier = LLMSemanticCitationVerifier()


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
    if (
        settings.generation_semantic_validation_enabled
        and validation_required
        and cited_claims
    ):
        try:
            semantic_result = semantic_verifier.verify(
                question=state.get("question", ""),
                claims=answer_structure.get("claims", []),
                contexts=state.get("generation_contexts", []),
            )
            validation, answer_structure = apply_semantic_support_validation(
                validation,
                answer_structure,
                semantic_result,
                support_threshold=(
                    settings.generation_semantic_support_threshold
                ),
            )
        except Exception as exc:
            semantic_reasons = list(validation.get("failure_reasons", []))
            if not settings.generation_semantic_validation_fail_open:
                semantic_reasons.append("semantic_validation_unavailable")
            validation = {
                **validation,
                "passed": not semantic_reasons,
                "failure_reasons": list(dict.fromkeys(semantic_reasons)),
                "semantic_support_checked": False,
                "semantic_validation_degraded": True,
                "semantic_validation_error": type(exc).__name__,
            }
            log_business_event(
                "semantic_citation_validation_failed",
                request_id=state.get("request_id"),
                session_id=state.get("session_id"),
                status="failed",
                error_message=str(exc),
                fail_open=settings.generation_semantic_validation_fail_open,
            )
    answer_structure["missing_information"] = list(
        state.get("missing_aspects", [])
    )
    validation["repair_attempted"] = state.get("generation_retry_count", 0) > 0
    validation["recommended_action"] = choose_validation_action(
        validation,
        repair_enabled=settings.generation_repair_enabled,
        retry_count=state.get("generation_retry_count", 0),
        answer_abstained=state.get("answer_abstained", False),
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
        citation_coverage=validation["citation_coverage"],
        claim_count=validation["claim_count"],
        invalid_citation_count=len(validation["invalid_citation_ids"]),
        semantic_support_checked=validation.get(
            "semantic_support_checked", False
        ),
        semantic_support_rate=validation.get("semantic_support_rate"),
        semantic_validation_degraded=validation.get(
            "semantic_validation_degraded", False
        ),
        recommended_action=validation["recommended_action"],
        generation_retry_count=state.get("generation_retry_count", 0),
    )
    return {
        "answer_validation": validation,
        "answer_validation_history": [dict(validation)],
        "answer_structure": answer_structure,
        "generation_quality_passed": bool(validation["passed"]),
    }


def route_after_answer_verifier(state: IndustrialRAGState) -> str:
    validation = state.get("answer_validation", {})
    action = validation.get("recommended_action") or choose_validation_action(
        validation,
        repair_enabled=settings.generation_repair_enabled,
        retry_count=state.get("generation_retry_count", 0),
        answer_abstained=state.get("answer_abstained", False),
    )
    if action == "llm_repair":
        return "repair"
    return "finalize"
