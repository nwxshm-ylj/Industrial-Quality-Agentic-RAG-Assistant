import app.graph.nodes.answer_repair_node as repair_module
import app.graph.nodes.answer_verifier_node as verifier_module
from app.graph.nodes.answer_repair_node import answer_repair_node
from app.graph.nodes.answer_verifier_node import (
    answer_verifier_node,
    route_after_answer_verifier,
)
from app.graph.nodes.finalize_answer_node import finalize_answer_node


class MockRepairGenerator:
    def repair_answer(self, **kwargs):
        assert kwargs["validation"]["passed"] is False
        return "优先检查相机曝光参数【资料1】。"


class MockSemanticVerifier:
    def verify(self, *, question, claims, contexts):
        return {
            "claims": [
                {
                    "claim_index": index,
                    "verdict": "supported",
                    "reason": "测试证据直接支持",
                }
                for index, claim in enumerate(claims)
                if claim.get("citation_ids")
            ]
        }


def main() -> None:
    original = repair_module.generator
    original_verifier = verifier_module.semantic_verifier
    state = {
        "request_id": "g3-test",
        "session_id": "g3-session",
        "question": "优先排查什么？",
        "intent": "rag",
        "draft_answer": "优先检查相机曝光参数。",
        "answer": "优先检查相机曝光参数。",
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
    try:
        verifier_module.semantic_verifier = MockSemanticVerifier()
        first = answer_verifier_node(state)
        state.update(first)
        assert first["generation_quality_passed"] is False
        assert route_after_answer_verifier(state) == "repair"

        repair_module.generator = MockRepairGenerator()
        state.update(answer_repair_node(state))
        assert state["generation_retry_count"] == 1

        second = answer_verifier_node(state)
        state.update(second)
        assert second["generation_quality_passed"] is True
        assert route_after_answer_verifier(state) == "finalize"

        final = finalize_answer_node(state)
        assert final["answer"] == "优先检查相机曝光参数【资料1】。"
        assert final["answer_abstained"] is False

        coverage_only_state = {
            **state,
            "draft_answer": "- 已证实的结论【资料1】。\n- 没有引用的扩展结论。",
            "answer": "- 已证实的结论【资料1】。\n- 没有引用的扩展结论。",
            "generation_retry_count": 0,
        }
        coverage_only_state.update(
            answer_verifier_node(coverage_only_state)
        )
        assert coverage_only_state["generation_quality_passed"] is False
        assert (
            coverage_only_state["answer_validation"]["recommended_action"]
            == "deterministic_prune"
        )
        assert route_after_answer_verifier(coverage_only_state) == "finalize"
        coverage_pruned = finalize_answer_node(coverage_only_state)
        assert coverage_pruned["answer_abstained"] is False
        assert coverage_pruned["citation_pruned"] is True
        assert coverage_pruned["answer_validation"]["repair_attempted"] is False
        assert "已证实的结论" in coverage_pruned["answer"]
        assert "扩展结论" not in coverage_pruned["answer"]

        failed_state = {
            **state,
            "draft_answer": "没有引用的结论。",
            "answer": "没有引用的结论。",
            "generation_retry_count": 1,
        }
        failed_state.update(answer_verifier_node(failed_state))
        refused = finalize_answer_node(failed_state)
        assert refused["answer_abstained"] is True
        assert "未通过引用一致性校验" in refused["answer"]

        partially_cited_state = {
            **state,
            "draft_answer": "- 已证实的结论【资料1】。\n- 没有引用的扩展结论。",
            "answer": "- 已证实的结论【资料1】。\n- 没有引用的扩展结论。",
            "generation_retry_count": 1,
        }
        partially_cited_state.update(
            answer_verifier_node(partially_cited_state)
        )
        assert partially_cited_state["generation_quality_passed"] is False
        pruned = finalize_answer_node(partially_cited_state)
        assert pruned["answer_abstained"] is False
        assert pruned["citation_pruned"] is True
        assert pruned["answer_validation"]["semantic_support_checked"] is True
        assert pruned["answer_validation"]["semantic_support_rate"] == 1.0
        assert "已证实的结论" in pruned["answer"]
        assert "扩展结论" not in pruned["answer"]
        assert pruned["answer_validation"]["passed"] is True
        print("Answer single-repair flow test passed")
    finally:
        repair_module.generator = original
        verifier_module.semantic_verifier = original_verifier


if __name__ == "__main__":
    main()
