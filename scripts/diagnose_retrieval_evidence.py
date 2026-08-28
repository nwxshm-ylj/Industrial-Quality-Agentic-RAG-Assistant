"""Diagnose retrieval and evidence rejection without invoking the answer LLM.

Examples:
    python -m scripts.diagnose_retrieval_evidence --question-id STD005
    python -m scripts.diagnose_retrieval_evidence --question "SOC 内控目标是多少？"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.graph.nodes.evidence_judge_node import evidence_judge_node
from app.rag.online_hybrid_retriever import build_online_hybrid_retriever


DEFAULT_DATASET = Path("data/eval/eval_questions.json")


def _load_question(path: Path, question_id: str) -> dict[str, Any]:
    items = json.loads(path.read_text(encoding="utf-8"))
    for item in items:
        if item.get("id") == question_id:
            return item
    raise KeyError(f"Question id not found in {path}: {question_id}")


def _summarize(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for rank, item in enumerate(items[:limit], start=1):
        text = " ".join(str(item.get("text") or "").split())
        output.append(
            {
                "rank": rank,
                "doc_id": item.get("doc_id"),
                "source": item.get("source"),
                "doc_type": item.get("doc_type"),
                "chunk_id": item.get("chunk_id"),
                "chunk_index": item.get("chunk_index"),
                "retrieval_source": item.get("retrieval_source"),
                "score": item.get("score"),
                "vector_score": item.get("vector_score"),
                "keyword_score": item.get("keyword_score"),
                "rrf_score": item.get("rrf_score"),
                "weighted_score": item.get("weighted_score"),
                "rerank_score": item.get("rerank_score"),
                "final_score_type": item.get("final_score_type"),
                "text_preview": text[:240],
            }
        )
    return output


def _source_rank(items: list[dict[str, Any]], expected: str | None) -> int | None:
    if not expected:
        return None
    needle = expected.casefold()
    for rank, item in enumerate(items, start=1):
        if needle in str(item.get("source") or "").casefold():
            return rank
    return None


def diagnose(
    question: str,
    *,
    expected_source: str | None = None,
    expected_doc_type: str | None = None,
    top_k: int = 5,
    candidate_k: int = 20,
) -> dict[str, Any]:
    retriever = build_online_hybrid_retriever()
    vector_results = retriever.vector_backend.search(question, top_k=candidate_k)
    keyword_results = retriever.keyword_backend.search(question, top_k=candidate_k)
    final_result = retriever.retrieve(
        question,
        top_k=top_k,
        vector_top_k=candidate_k,
        keyword_top_k=candidate_k,
        rerank_candidate_k=max(top_k, candidate_k),
    )
    contexts = final_result["contexts"]
    evidence = evidence_judge_node(
        {
            "question": question,
            "rewritten_query": question,
            "contexts": contexts,
            "retrieval_metadata": final_result.get("metadata", {}),
            "retry_count": 0,
        }
    )
    return {
        "question": question,
        "expectation": {
            "source_contains": expected_source,
            "doc_type": expected_doc_type,
        },
        "environment": {
            "embedding_provider": retriever.vector_backend.embedding_provider.provider_name,
            "embedding_model": retriever.vector_backend.embedding_provider.model_name,
            "embedding_dimension": retriever.vector_backend.embedding_provider.dimension,
            "embedding_index_version": retriever.vector_backend.embedding_provider.index_version,
            "qdrant_collection": retriever.vector_backend.collection_name,
            "qdrant_alias": retriever.vector_backend.collection_alias,
            "qdrant_alias_target": retriever.vector_backend.get_alias_target(),
            "keyword_index": retriever.keyword_backend.index_name,
            "fusion_strategy": retriever.fusion_strategy,
            "reranker_enabled": retriever.use_reranker,
        },
        "stage_summary": {
            "vector_result_count": len(vector_results),
            "keyword_result_count": len(keyword_results),
            "final_result_count": len(contexts),
            "expected_source_vector_rank": _source_rank(vector_results, expected_source),
            "expected_source_keyword_rank": _source_rank(keyword_results, expected_source),
            "expected_source_final_rank": _source_rank(contexts, expected_source),
        },
        "retrieval_metadata": final_result.get("metadata", {}),
        "evidence": {
            "enough": evidence.get("evidence_enough"),
            "confidence": evidence.get("evidence_confidence"),
            "score": evidence.get("evidence_score"),
            "reasons": evidence.get("evidence_reasons", []),
            "missing_aspects": evidence.get("missing_aspects", []),
            "abstain_reason": evidence.get("abstain_reason"),
        },
        "vector_results": _summarize(vector_results, candidate_k),
        "keyword_results": _summarize(keyword_results, candidate_k),
        "final_results": _summarize(contexts, top_k),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--question-id")
    source.add_argument("--question")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    item: dict[str, Any] = {}
    if args.question_id:
        item = _load_question(args.dataset, args.question_id)
    question = args.question or str(item["question"])
    report = diagnose(
        question,
        expected_source=item.get("expected_source_contains"),
        expected_doc_type=item.get("expected_doc_type"),
        top_k=args.top_k,
        candidate_k=args.candidate_k,
    )
    report["question_id"] = args.question_id
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"Diagnostic report written: {args.output}")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
