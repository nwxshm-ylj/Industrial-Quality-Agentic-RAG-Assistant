from __future__ import annotations

from app.core.logger import log_business_event, observe_node
from app.graph.state import IndustrialRAGState
from app.rag.generator import AnswerGenerator


generator = AnswerGenerator()


@observe_node("answer_repair")
def answer_repair_node(state: IndustrialRAGState) -> dict:
    draft = state.get("draft_answer") or state.get("answer", "")
    repair_error = None
    try:
        repaired = generator.repair_answer(
            question=state.get("question", ""),
            draft_answer=draft,
            contexts=state.get("generation_contexts", []),
            validation=state.get("answer_validation", {}),
            missing_aspects=state.get("missing_aspects", []),
        )
    except Exception as exc:
        repaired = draft
        repair_error = type(exc).__name__
        log_business_event(
            "answer_repair_failed",
            request_id=state.get("request_id"),
            session_id=state.get("session_id"),
            status="failed",
            error_message=str(exc),
        )
    else:
        log_business_event(
            "answer_repair_completed",
            request_id=state.get("request_id"),
            session_id=state.get("session_id"),
            status="success",
            generation_retry_count=state.get("generation_retry_count", 0) + 1,
        )
    return {
        "draft_answer": repaired,
        "answer": repaired,
        "generation_retry_count": state.get("generation_retry_count", 0) + 1,
        "generation_repair_error": repair_error,
    }
