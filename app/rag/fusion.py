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


def weighted_score_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    *,
    vector_weight: float = 0.65,
    keyword_weight: float = 0.35,
) -> list[dict]:
    """Fuse normalized scores without comparing incompatible raw score scales."""

    if vector_weight < 0 or keyword_weight < 0:
        raise ValueError("fusion weights cannot be negative")
    total_weight = vector_weight + keyword_weight
    if total_weight <= 0:
        raise ValueError("at least one fusion weight must be greater than zero")
    normalized_vector_weight = vector_weight / total_weight
    normalized_keyword_weight = keyword_weight / total_weight

    merged: dict[str, dict] = {}
    _merge_weighted_results(
        merged,
        vector_results,
        source="vector",
        weight=normalized_vector_weight,
    )
    _merge_weighted_results(
        merged,
        keyword_results,
        source="keyword",
        weight=normalized_keyword_weight,
    )

    results: list[dict] = []
    for item in merged.values():
        sources = item.pop("_retrieval_sources")
        item["retrieval_source"] = "+".join(sorted(sources))
        item["weighted_score"] = float(item.get("weighted_score", 0.0))
        item["hybrid_score"] = item["weighted_score"]
        item["score"] = item["weighted_score"]
        item["evidence_signal_score"] = item["weighted_score"]
        item["final_score_type"] = "weighted_score"
        results.append(item)

    results.sort(key=lambda result: result["weighted_score"], reverse=True)
    return results


def multimodal_rrf_fusion(
    text_results: list[dict],
    multimodal_results: list[dict],
    *,
    rrf_k: int = 60,
) -> list[dict]:
    """Fuse the established text ranking with an isolated multimodal ranking."""

    if rrf_k <= 0:
        raise ValueError("rrf_k must be greater than zero")
    merged: dict[str, dict] = {}
    for source, results in (
        ("text_hybrid", text_results),
        ("multimodal", multimodal_results),
    ):
        for rank, result in enumerate(results, start=1):
            key = _result_key(result)
            if key not in merged:
                merged[key] = {
                    **result,
                    "cross_modal_rrf_score": 0.0,
                    "text_hybrid_score": None,
                    "multimodal_score": None,
                    "_retrieval_sources": set(),
                }
            item = merged[key]
            raw_score = float(result.get("score", 0.0))
            item[f"{source}_score"] = raw_score
            item["cross_modal_rrf_score"] += 1.0 / (rrf_k + rank)
            item["_retrieval_sources"].add(source)

    output = []
    for item in merged.values():
        sources = item.pop("_retrieval_sources")
        item["retrieval_source"] = "+".join(sorted(sources))
        item["score"] = item["cross_modal_rrf_score"]
        item["hybrid_score"] = item["cross_modal_rrf_score"]
        item["evidence_signal_score"] = item["cross_modal_rrf_score"]
        item["final_score_type"] = "cross_modal_rrf_score"
        output.append(item)
    output.sort(key=lambda item: item["cross_modal_rrf_score"], reverse=True)
    return output


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


def _merge_weighted_results(
    merged: dict[str, dict],
    results: list[dict],
    *,
    source: str,
    weight: float,
) -> None:
    normalized_scores = _min_max_normalize(results)
    for result, normalized_score in zip(results, normalized_scores):
        key = _result_key(result)
        if key not in merged:
            merged[key] = {
                **result,
                "vector_score": None,
                "keyword_score": None,
                "bm25_score": None,
                "weighted_score": 0.0,
                "_retrieval_sources": set(),
            }

        item = merged[key]
        raw_score = float(result.get("score", 0.0))
        if source == "vector":
            item["vector_score"] = raw_score
        else:
            item["keyword_score"] = raw_score
            item["bm25_score"] = raw_score
        item["weighted_score"] += weight * normalized_score
        item["_retrieval_sources"].add(source)


def _min_max_normalize(results: list[dict]) -> list[float]:
    if not results:
        return []
    scores = [float(item.get("score", 0.0)) for item in results]
    minimum = min(scores)
    maximum = max(scores)
    if maximum == minimum:
        return [1.0 for _ in scores]
    return [(score - minimum) / (maximum - minimum) for score in scores]


def _result_key(result: dict) -> str:
    asset_id = result.get("asset_id")
    if asset_id:
        return f"asset:{asset_id}"
    chunk_id = result.get("chunk_id")
    if chunk_id:
        return str(chunk_id)
    return f"{result.get('source', '')}:{result.get('text', '')}"
