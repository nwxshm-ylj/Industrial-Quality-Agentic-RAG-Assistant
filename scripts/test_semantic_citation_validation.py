"""Regression guard for line validation plus claim policy propagation."""

from __future__ import annotations

from app.generation import build_citation_safe_answer, validate_answer_citations


def main() -> None:
    contexts = [
        {
            "citation_label": "资料1",
            "text": "ZP8 ECOS阶段要求电瓶SOC内控目标达到72%。",
        },
        {
            "citation_label": "资料2",
            "text": "本章节介绍车身尺寸测量室职责。",
        },
    ]
    validation, structure = validate_answer_citations(
        "- 电瓶SOC内控目标为72%【资料1】。\n"
        "- 电瓶SOC内控目标为90%【资料2】。",
        contexts,
    )
    # The deterministic layer still checks label existence. Semantic checking
    # is applied by Answer Verifier according to policy and configuration.
    assert validation["passed"] is True
    assert validation["semantic_support_checked"] is False
    assert validation["semantic_support_rate"] is None
    assert validation["claim_count"] == 2
    assert all(claim["citation_required"] for claim in structure["claims"])
    safe_answer = build_citation_safe_answer(structure)
    assert "72%" in safe_answer
    assert "90%" in safe_answer
    print("Semantic citation policy propagation test passed")


if __name__ == "__main__":
    main()
