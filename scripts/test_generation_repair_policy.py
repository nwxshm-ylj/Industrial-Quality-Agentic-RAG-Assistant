"""Dependency-free regression test for the Phase G3.5 repair policy."""

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
    "citation_validator_under_test",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _action(reasons: list[str], *, retry_count: int = 0) -> str:
    return MODULE.choose_validation_action(
        {"passed": not reasons, "failure_reasons": reasons},
        repair_enabled=True,
        retry_count=retry_count,
        answer_abstained=False,
    )


def main() -> None:
    assert _action([]) == "finalize"
    assert (
        _action(["citation_coverage_below_threshold"])
        == "deterministic_prune"
    )
    assert _action(["semantic_unsupported_claims"]) == "llm_repair"
    assert _action(["no_valid_citations"]) == "llm_repair"
    assert _action(["semantic_unsupported_claims"], retry_count=1) == "finalize"

    validation, structure = MODULE.validate_answer_citations(
        "- 已证实的结论【资料1】。\n- 未引用的扩展结论。",
        [{"citation_label": "资料1", "text": "已证实的结论"}],
    )
    assert validation["failure_reasons"] == [
        "citation_coverage_below_threshold"
    ]
    structure["claims"][0]["claim_type"] = "supported"
    safe_answer = MODULE.build_citation_safe_answer(structure)
    assert "已证实的结论" in safe_answer
    assert "扩展结论" not in safe_answer
    print("Generation repair policy test passed")


if __name__ == "__main__":
    main()
