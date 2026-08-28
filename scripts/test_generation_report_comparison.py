from __future__ import annotations

from scripts.compare_generation_reports import build_gates


def main() -> None:
    baseline = {
        "metrics": {"overall_pass_rate": 0.72},
        "results": [],
    }
    passing_candidate = {
        "metrics": {
            "overall_pass_rate": 0.75,
            "citation_validation_pass_rate": 0.96,
            "semantic_support_pass_rate": 0.97,
            "abstention_accuracy": 0.98,
            "llm_repair_selection_rate": 0.20,
            "avg_latency_ms": 14000,
            "p95_latency_ms": 29000,
        },
        "results": [{"id": "T1", "all_ok": True}],
    }
    gates = build_gates(baseline, passing_candidate)
    assert gates
    assert all(item["passed"] for item in gates)

    failing_candidate = {
        **passing_candidate,
        "metrics": {
            **passing_candidate["metrics"],
            "overall_pass_rate": 0.60,
            "llm_repair_selection_rate": 0.40,
        },
    }
    failed = [
        item["name"]
        for item in build_gates(baseline, failing_candidate)
        if not item["passed"]
    ]
    assert "总体通过率不回退" in failed
    assert "LLM 修复选择率" in failed
    print("Generation report comparison test passed")


if __name__ == "__main__":
    main()
