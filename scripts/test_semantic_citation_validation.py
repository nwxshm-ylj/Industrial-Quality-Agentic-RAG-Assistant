from __future__ import annotations

from app.generation import (
    apply_semantic_support_validation,
    build_citation_safe_answer,
    validate_answer_citations,
)
from app.generation.semantic_citation_validator import (
    LLMSemanticCitationVerifier,
)


def main() -> None:
    contexts = [
        {
            "citation_label": "资料1",
            "source": "电子电气标准.pdf",
            "text": "ZP8 ECOS阶段要求电瓶SOC内控目标达到72%。",
        },
        {
            "citation_label": "资料2",
            "source": "无关资料.pdf",
            "text": "本章节介绍车身尺寸测量室职责。",
        },
    ]
    validation, structure = validate_answer_citations(
        "- 电瓶SOC内控目标为72%。【资料1】\n- 电瓶SOC内控目标为90%。【资料2】",
        contexts,
    )
    assert validation["passed"] is True
    semantic, structure = apply_semantic_support_validation(
        validation,
        structure,
        {
            "claims": [
                {"claim_index": 0, "verdict": "supported", "reason": "证据直接给出72%"},
                {"claim_index": 1, "verdict": "unsupported", "reason": "证据未提及90%"},
            ]
        },
    )
    assert semantic["passed"] is False
    assert semantic["semantic_support_checked"] is True
    assert semantic["semantic_support_rate"] == 0.5
    assert semantic["semantic_unsupported_claim_count"] == 1
    safe_answer = build_citation_safe_answer(structure)
    assert "72%" in safe_answer
    assert "90%" not in safe_answer

    parsed = LLMSemanticCitationVerifier._parse_response(
        "```json\n{\"claims\":[{\"claim_index\":0,\"verdict\":\"partial\",\"reason\":\"只支持部分\"}]}\n```",
        expected_claims=[{"claim_index": 0}],
    )
    assert parsed["claims"][0]["verdict"] == "partial"
    print("Semantic citation validation test passed")


if __name__ == "__main__":
    main()
