from app.graph.nodes.answer_verifier_node import (
    answer_verifier_node,
    route_after_answer_verifier,
)
from app.graph.nodes.finalize_answer_node import finalize_answer_node


def _state(answer: str) -> dict:
    return {
        "request_id": "line-validation-test",
        "session_id": "line-validation-session",
        "question": "优先排查什么？",
        "intent": "rag",
        "draft_answer": answer,
        "answer": answer,
        "answer_abstained": False,
        "generation_contexts": [
            {
                "citation_label": "资料1",
                "text": "应优先检查相机曝光参数。",
            }
        ],
        "missing_aspects": [],
        "generation_retry_count": 0,
    }


def main() -> None:
    state = _state(
        "### 排查\n"
        "- 优先检查相机曝光参数【资料1】。\n"
        "- 同时更换全部相机。"
    )
    state.update(answer_verifier_node(state))
    assert state["generation_quality_passed"] is False
    assert state["answer_validation"]["recommended_action"] == (
        "deterministic_prune"
    )
    assert state["answer_validation"]["semantic_support_checked"] is False
    assert state["answer_validation"]["repair_attempted"] is False
    assert state["answer_validation"]["claim_count"] == 2
    assert route_after_answer_verifier(state) == "finalize"

    final = finalize_answer_node(state)
    assert final["answer_abstained"] is False
    assert final["citation_pruned"] is True
    assert "曝光参数" in final["answer"]
    assert "更换全部相机" not in final["answer"]
    assert final["answer_validation"]["passed"] is True
    assert final["answer_validation"]["removed_line_count"] == 1

    failed_state = _state("没有引用的结论。")
    failed_state.update(answer_verifier_node(failed_state))
    refused = finalize_answer_node(failed_state)
    assert refused["answer_abstained"] is True
    assert "没有保留下来可验证的资料引用" in refused["answer"]
    assert refused["answer_validation"]["repair_attempted"] is False
    print("Single-generation line validation flow test passed")


if __name__ == "__main__":
    main()
