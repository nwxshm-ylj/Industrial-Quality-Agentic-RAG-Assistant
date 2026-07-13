from collections.abc import Iterable


def reciprocal_rank_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    *,
    rrf_k: int = 60,
) -> list[dict]:
    """Fuse ranked online retrieval results while preserving API fields."""

    if rrf_k <= 0:
        raise ValueError("rrf_k must be greater than zero")

    merged: dict[str, dict] = {}
    _merge_ranked_results(merged, vector_results, "vector", rrf_k)
    _merge_ranked_results(merged, keyword_results, "keyword", rrf_k)

    results: list[dict] = []
    for item in merged.values():
        sources = item.pop("_retrieval_sources")
        item["retrieval_source"] = "+".join(sorted(sources))
        item["rrf_score"] = float(item.get("rrf_score", 0.0))
        item["hybrid_score"] = item["rrf_score"]
        item["score"] = item["rrf_score"]
        item["evidence_signal_score"] = (
            item.get("vector_score")
            if item.get("vector_score") is not None
            else item.get("keyword_score")
        )
        item["final_score_type"] = "rrf_score"
        results.append(item)

    results.sort(key=lambda result: result["rrf_score"], reverse=True)
    return results


def _merge_ranked_results(
    merged: dict[str, dict],
    results: Iterable[dict],
    source: str,
    rrf_k: int,
) -> None:
    for rank, result in enumerate(results, start=1):
        key = _result_key(result)
        if key not in merged:
            merged[key] = {
                **result,
                "vector_score": None,
                "keyword_score": None,
                "bm25_score": None,
                "rrf_score": 0.0,
                "_retrieval_sources": set(),
            }

        item = merged[key]
        raw_score = float(result.get("score", 0.0))
        if source == "vector":
            item["vector_score"] = raw_score
        else:
            item["keyword_score"] = raw_score
            # Additive compatibility for existing clients during migration.
            item["bm25_score"] = raw_score

        item["rrf_score"] += 1.0 / (rrf_k + rank)
        item["_retrieval_sources"].add(source)


def _result_key(result: dict) -> str:
    chunk_id = result.get("chunk_id")
    if chunk_id:
        return str(chunk_id)
    return f"{result.get('source', '')}:{result.get('text', '')}"
