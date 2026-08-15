from __future__ import annotations

from pathlib import Path

from app.prompting.registry import PromptRegistry


def main() -> None:
    catalog = Path("prompts/catalog")
    stable = PromptRegistry(
        catalog_path=catalog,
        release_path="prompts/releases/stable.yaml",
    )
    candidate = PromptRegistry(
        catalog_path=catalog,
        release_path="prompts/releases/candidate.yaml",
    )

    stable_metadata = stable.release_metadata()
    candidate_metadata = candidate.release_metadata()
    expected_components = {
        "intent_router",
        "query_rewriter_initial",
        "query_rewriter_retry",
        "answer_generator",
        "answer_repair",
        "semantic_citation_verifier",
        "sql_generator",
    }
    assert set(stable_metadata["versions"]) == expected_components
    assert stable_metadata["channel"] == "stable"
    assert candidate_metadata["channel"] == "candidate"
    assert stable_metadata["versions"]["answer_generator"] == "1.2.0"
    assert stable_metadata["versions"]["answer_repair"] == "1.0.0"
    assert stable_metadata["versions"]["semantic_citation_verifier"] == "1.0.0"
    assert candidate_metadata["versions"]["answer_generator"] == "1.2.0"
    assert stable_metadata["versions"]["intent_router"] == "1.1.0"
    assert stable_metadata["versions"]["query_rewriter_initial"] == "1.1.0"
    assert stable_metadata["versions"]["query_rewriter_retry"] == "1.1.0"
    for component in expected_components - {"answer_generator"}:
        assert (
            stable_metadata["versions"][component]
            == candidate_metadata["versions"][component]
        )

    for reference in stable.references().values():
        assert len(reference.content_hash) == 64
        assert reference.release_id == stable_metadata["release_id"]

    candidate_answer = candidate.references()["answer_generator"]
    assert candidate_answer.version == "1.2.0"
    assert candidate_answer.release_id == candidate_metadata["release_id"]
    rendered_candidate = candidate.render(
        "answer_generator",
        {
            "memory_text": "无历史对话。",
            "question": "案例的原因和措施是什么？",
            "context_text": "资料1给出了直接原因和整改措施。",
            "intent": "rag",
            "evidence_text": "证据是否通过门禁：是",
        },
    )
    assert "不得用常识补齐" in rendered_candidate.messages[0].content
    assert "不超过800个中文字符" in rendered_candidate.messages[0].content
    rendered_repair = candidate.render(
        "answer_repair",
        {
            "question": "优先排查什么？",
            "draft_answer": "优先检查相机。",
            "validation_text": '{"passed": false}',
            "missing_aspects": "无",
            "context_text": "【资料1】应优先检查相机曝光参数。",
        },
    )
    assert "只修复引用契约" in rendered_repair.messages[0].content
    rendered_semantic = candidate.render(
        "semantic_citation_verifier",
        {
            "question": "SOC目标是多少？",
            "claim_evidence_json": (
                '[{"claim_index":0,"claim":"SOC目标为72%",'
                '"evidence":[{"citation_id":"资料1","text":"SOC目标72%"}]}]'
            ),
        },
    )
    assert "supported" in rendered_semantic.messages[0].content

    archived = PromptRegistry(
        catalog_path=catalog,
        release_path="prompts/releases/industrial-prompts-2026-07-14.1.yaml",
    )
    assert archived.release_metadata()["versions"]["answer_generator"] == "1.0.0"

    print("Prompt Registry test passed")


if __name__ == "__main__":
    main()
