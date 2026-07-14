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
        "sql_generator",
    }
    assert set(stable_metadata["versions"]) == expected_components
    assert stable_metadata["channel"] == "stable"
    assert candidate_metadata["channel"] == "candidate"
    assert stable_metadata["versions"] == candidate_metadata["versions"]

    for reference in stable.references().values():
        assert reference.version == "1.0.0"
        assert len(reference.content_hash) == 64
        assert reference.release_id == stable_metadata["release_id"]

    print("Prompt Registry test passed")


if __name__ == "__main__":
    main()
