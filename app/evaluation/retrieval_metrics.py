from __future__ import annotations

from math import log2
from pathlib import PurePath
from statistics import mean
from typing import Any, Iterable


SUPPORTED_RELEVANCE_FIELDS = {"doc_id", "chunk_id", "source"}


def normalize_k_values(k_values: Iterable[int], *, top_k: int) -> list[int]:
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    normalized = sorted({int(value) for value in k_values})
    if not normalized or normalized[0] <= 0:
        raise ValueError("k_values must contain positive integers")
    if len(normalized) > 10:
        raise ValueError("k_values cannot contain more than 10 values")
    if normalized[-1] > top_k:
        raise ValueError("k_values cannot contain a value greater than top_k")
    return normalized


def normalize_identifier(value: Any, relevance_field: str) -> str:
    if relevance_field not in SUPPORTED_RELEVANCE_FIELDS:
        raise ValueError(
            "relevance_field must be one of: doc_id, chunk_id, source"
        )
    normalized = str(value or "").strip().replace("\\", "/")
    if relevance_field == "source":
        normalized = PurePath(normalized).name
    return normalized.casefold()


def unique_ranked_identifiers(
    results: list[dict[str, Any]],
    *,
    relevance_field: str,
) -> list[str]:
    ranked: list[str] = []
    seen: set[str] = set()
    for result in results:
        identifier = normalize_identifier(
            result.get(relevance_field), relevance_field
        )
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        ranked.append(identifier)
    return ranked


def calculate_rank_metrics(
    results: list[dict[str, Any]],
    *,
    relevant_ids: Iterable[str],
    relevance_field: str,
    k_values: Iterable[int],
    top_k: int,
) -> dict[str, float]:
    normalized_k = normalize_k_values(k_values, top_k=top_k)
    relevant = {
        normalize_identifier(value, relevance_field)
        for value in relevant_ids
        if normalize_identifier(value, relevance_field)
    }
    if not relevant:
        raise ValueError("relevant_ids must contain at least one identifier")

    ranked = unique_ranked_identifiers(
        results,
        relevance_field=relevance_field,
    )
    metrics: dict[str, float] = {}
    for k in normalized_k:
        top_results = ranked[:k]
        relevance = [1 if item in relevant else 0 for item in top_results]
        relevant_hits = len(set(top_results) & relevant)
        first_relevant_rank = next(
            (rank for rank, item in enumerate(top_results, start=1)
             if item in relevant),
            None,
        )
        dcg = sum(
            value / log2(rank + 1)
            for rank, value in enumerate(relevance, start=1)
        )
        ideal_hits = min(len(relevant), k)
        idcg = sum(1.0 / log2(rank + 1) for rank in range(1, ideal_hits + 1))

        metrics[f"precision@{k}"] = round(relevant_hits / k, 6)
        metrics[f"recall@{k}"] = round(relevant_hits / len(relevant), 6)
        metrics[f"hit_rate@{k}"] = 1.0 if relevant_hits else 0.0
        metrics[f"mrr@{k}"] = (
            round(1.0 / first_relevant_rank, 6)
            if first_relevant_rank is not None
            else 0.0
        )
        metrics[f"ndcg@{k}"] = round(dcg / idcg, 6) if idcg else 0.0
    return metrics


def aggregate_rank_metrics(
    item_metrics: list[dict[str, float]],
) -> dict[str, float]:
    if not item_metrics:
        return {}
    keys = sorted({key for item in item_metrics for key in item})
    return {
        key: round(mean(float(item.get(key, 0.0)) for item in item_metrics), 6)
        for key in keys
    }


def percentile(values: Iterable[float], quantile: float) -> float:
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * quantile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return (
        ordered[lower_index]
        + (ordered[upper_index] - ordered[lower_index]) * fraction
    )


def summarize_latency(values: Iterable[float]) -> dict[str, float | int]:
    normalized = [max(float(value), 0.0) for value in values]
    if not normalized:
        return {
            "count": 0,
            "min_ms": 0.0,
            "avg_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }
    return {
        "count": len(normalized),
        "min_ms": round(min(normalized), 2),
        "avg_ms": round(mean(normalized), 2),
        "p50_ms": round(percentile(normalized, 0.50), 2),
        "p95_ms": round(percentile(normalized, 0.95), 2),
        "p99_ms": round(percentile(normalized, 0.99), 2),
        "max_ms": round(max(normalized), 2),
    }
