"""Dependency-free regression test for deterministic line pruning."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "generation"
    / "citation_validator.py"
)
SPEC = importlib.util.spec_from_file_location(
    "citation_validator_under_test", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _action(reasons: list[str]) -> str:
    return MODULE.choose_validation_action(
        {"passed": not reasons, "failure_reasons": reasons},
        repair_enabled=True,
        retry_count=0,
        answer_abstained=False,
    )


def main() -> None:
    assert _action([]) == "finalize"
    assert _action(["uncited_answer_lines"]) == "deterministic_prune"
    assert _action(["invalid_citation_ids"]) == "deterministic_prune"
    assert _action(["no_valid_citations"]) == "deterministic_prune"

    validation, structure = MODULE.validate_answer_citations(
        "### 结论\n"
        "- 已证实的结论【资料1】。\n"
        "- 未引用的扩展结论。\n"
        "### 空章节\n"
        "- 错误编号【资料9】。",
        [{"citation_label": "资料1", "text": "已证实的结论"}],
    )
    assert validation["passed"] is False
    assert validation["line_count"] == 3
    assert validation["claim_count"] == 3
    safe_answer = MODULE.build_citation_safe_answer(structure)
    assert "### 结论" in safe_answer
    assert "已证实的结论" in safe_answer
    assert "扩展结论" not in safe_answer
    assert "### 空章节" not in safe_answer
    assert "资料9" not in safe_answer
    print("Deterministic line pruning policy test passed")


if __name__ == "__main__":
    main()
