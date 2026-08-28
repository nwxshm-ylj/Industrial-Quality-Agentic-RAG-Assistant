from __future__ import annotations

import app.graph.nodes.answer_verifier_node as verifier_module
from app.core.config import settings
from app.generation.semantic_citation_validator import LLMSemanticCitationVerifier
from app.graph.nodes.finalize_answer_node import finalize_answer_node


class FailingSemanticVerifier:
    def verify(self, **kwargs):
        del kwargs
        raise RuntimeError("mock semantic verifier unavailable")


def _state(answer: str) -> dict:
    return {
        "request_id": "generation-trust-p0",
        "session_id": "generation-trust-p0-session",
        "question": "装配要求是什么？",
        "intent": "rag",
        "draft_answer": answer,
        "answer": answer,
        "answer_abstained": False,
        "generation_contexts": [
            {
                "citation_label": "资料1",
                "source": "mock-standard.pdf",
                "text": "装配记录包含相关要求。",
            }
        ],
        "missing_aspects": [],
        "generation_retry_count": 0,
    }


def main() -> None:
    payload = LLMSemanticCitationVerifier._build_payload(
        [
            {
                "text": "安全扭矩阈值为80Nm。",
                "citation_ids": ["资料1"],
                "evidence_policy": "strict",
                "claim_category": "fact",
                "citation_required": True,
            }
        ],
        _state("unused")["generation_contexts"],
    )
    assert set(payload[0]) == {
        "claim_index",
        "claim",
        "evidence_policy",
        "claim_category",
        "citation_required",
        "evidence",
    }
    assert payload[0]["evidence_policy"] == "strict"
    assert payload[0]["claim_category"] == "fact"
    assert payload[0]["citation_required"] is True

    original_enabled = settings.generation_semantic_validation_enabled
    original_fail_open = settings.generation_semantic_validation_fail_open
    original_verifier = verifier_module.semantic_verifier
    try:
        verifier_module.semantic_verifier = FailingSemanticVerifier()
        settings.generation_semantic_validation_enabled = True
        settings.generation_semantic_validation_fail_open = True

        strict_exception = verifier_module.answer_verifier_node(
            _state("安全扭矩阈值为80Nm【资料1】。")
        )
        strict_validation = strict_exception["answer_validation"]
        assert strict_exception["generation_quality_passed"] is False
        assert "strict_semantic_validation_unavailable" in (
            strict_validation["failure_reasons"]
        )
        assert strict_validation["semantic_validation_fail_open_configured"] is True
        assert strict_validation["semantic_validation_fail_open_effective"] is False

        standard_exception = verifier_module.answer_verifier_node(
            _state("装配记录包含相关要求【资料1】。")
        )
        standard_validation = standard_exception["answer_validation"]
        assert standard_exception["generation_quality_passed"] is True
        assert standard_validation["semantic_validation_degraded"] is True
        assert standard_validation["semantic_validation_fail_open_effective"] is True

        settings.generation_semantic_validation_enabled = False
        strict_disabled = verifier_module.answer_verifier_node(
            _state("法规禁止带故障放行【资料1】。")
        )
        assert strict_disabled["generation_quality_passed"] is False
        assert "strict_semantic_validation_unavailable" in (
            strict_disabled["answer_validation"]["failure_reasons"]
        )
        final_state = _state("法规禁止带故障放行【资料1】。")
        final_state.update(strict_disabled)
        refused = finalize_answer_node(final_state)
        assert refused["generation_quality_passed"] is False
        assert refused["answer_abstained"] is True
        assert "strict_semantic_validation_unavailable" in refused["answer"]
        print("Generation trust P0 mock tests passed")
    finally:
        settings.generation_semantic_validation_enabled = original_enabled
        settings.generation_semantic_validation_fail_open = original_fail_open
        verifier_module.semantic_verifier = original_verifier


if __name__ == "__main__":
    main()
