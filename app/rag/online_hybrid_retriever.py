from __future__ import annotations

import re
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.logger import log_business_event
from app.core.metrics import record_retrieval
from app.core.telemetry import traced_span
from app.core.telemetry_context import add_retrieval_usage_event
from app.observability.usage_models import RetrievalUsageEvent
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.fusion import reciprocal_rank_fusion, weighted_score_fusion
from app.rag.retrieval_filters import RetrievalFilter
from app.rag.search_backends.base import (
    KeywordSearchBackend,
    KeywordSearchError,
    VectorSearchBackend,
)
from app.rag.search_backends.opensearch_backend import OpenSearchKeywordBackend
from app.rag.search_backends.qdrant_backend import QdrantVectorSearchBackend


class OnlineHybridRetriever:
    def __init__(
        self,
        vector_backend: VectorSearchBackend,
        keyword_backend: KeywordSearchBackend,
        *,
        degraded_mode: str = "vector_only",
        rrf_k: int = 60,
        fusion_strategy: str = "rrf",
        vector_weight: float = 0.65,
        keyword_weight: float = 0.35,
        use_reranker: bool = False,
        reranker: Any | None = None,
        reranker_fail_open: bool = True,
        neighbor_expansion_enabled: bool = False,
        neighbor_seed_k: int = 5,
        neighbor_window: int = 1,
        neighbor_max_per_seed: int = 1,
    ) -> None:
        if degraded_mode != "vector_only":
            raise ValueError(
                f"Unsupported HYBRID_DEGRADED_MODE: {degraded_mode}"
            )
        self.vector_backend = vector_backend
        self.keyword_backend = keyword_backend
        self.degraded_mode = degraded_mode
        self.rrf_k = rrf_k
        self.fusion_strategy = fusion_strategy.strip().lower()
        if self.fusion_strategy not in {"rrf", "weighted"}:
            raise ValueError(
                f"Unsupported RETRIEVAL_FUSION_STRATEGY: {fusion_strategy}"
            )
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.use_reranker = use_reranker
        self.reranker = reranker
        self.reranker_fail_open = reranker_fail_open
        self.neighbor_expansion_enabled = neighbor_expansion_enabled
        self.neighbor_seed_k = max(1, neighbor_seed_k)
        self.neighbor_window = max(1, neighbor_window)
        self.neighbor_max_per_seed = max(1, neighbor_max_per_seed)

        if self.use_reranker and self.reranker is None:
            try:
                from app.rag.reranker import IndustrialReranker

                self.reranker = IndustrialReranker()
            except Exception as exc:
                log_business_event(
                    "reranker_unavailable",
                    status="degraded",
                    error_message=str(exc),
                )
                self.use_reranker = False

    def retrieve(
        self,
        question: str,
        *,
        top_k: int = 5,
        vector_top_k: int = 20,
        keyword_top_k: int = 20,
        rerank_candidate_k: int = 20,
        filters: RetrievalFilter | dict[str, Any] | None = None,
    ) -> dict:
        started_at = perf_counter()
        vector_results: list[dict] = []
        keyword_results: list[dict] = []
        merged: list[dict] = []
        degraded = False
        degraded_reason = None
        degraded_components: list[str] = []
        reranker_degraded = False
        vector_latency_ms = 0.0
        keyword_latency_ms = 0.0
        fusion_latency_ms = 0.0
        reranker_latency_ms = 0.0
        neighbor_expansion_latency_ms = 0.0
        neighbor_expansion_degraded = False
        neighbor_expansion_reason = None
        neighbor_added_count = 0
        retrieval_filter = (
            filters
            if isinstance(filters, RetrievalFilter)
            else RetrievalFilter.from_mapping(filters)
        )

        try:
            vector_started_at = perf_counter()
            with traced_span(
                "retrieval.qdrant_search",
                attributes={"rag.top_k": vector_top_k},
            ):
                vector_results = self.vector_backend.search(
                    question,
                    top_k=vector_top_k,
                    filters=retrieval_filter,
                )
            vector_latency_ms = (perf_counter() - vector_started_at) * 1000

            keyword_started_at = perf_counter()
            try:
                with traced_span(
                    "retrieval.opensearch_search",
                    attributes={"rag.top_k": keyword_top_k},
                ):
                    keyword_results = self.keyword_backend.search(
                        question,
                        top_k=keyword_top_k,
                        filters=retrieval_filter,
                    )
            except KeywordSearchError as exc:
                if self.degraded_mode != "vector_only":
                    raise
                degraded = True
                degraded_reason = str(exc)
                degraded_components.append("keyword")
                log_business_event(
                    "hybrid_search_degraded",
                    status="degraded",
                    error_message=degraded_reason,
                    degraded=True,
                    degraded_reason=degraded_reason,
                    retrieval_mode="vector_only",
                )
            finally:
                keyword_latency_ms = (
                    perf_counter() - keyword_started_at
                ) * 1000

            fusion_started_at = perf_counter()
            with traced_span(
                "retrieval.rrf_fusion",
                attributes={"rag.rrf_k": self.rrf_k},
            ):
                if self.fusion_strategy == "weighted":
                    merged = weighted_score_fusion(
                        vector_results,
                        keyword_results,
                        vector_weight=self.vector_weight,
                        keyword_weight=self.keyword_weight,
                    )
                else:
                    merged = reciprocal_rank_fusion(
                        vector_results,
                        keyword_results,
                        rrf_k=self.rrf_k,
                    )
            fusion_latency_ms = (perf_counter() - fusion_started_at) * 1000
            candidates = merged[:rerank_candidate_k]

            if self.use_reranker and self.reranker is not None and candidates:
                reranker_started_at = perf_counter()
                try:
                    with traced_span(
                        "retrieval.reranker",
                        attributes={"rag.candidate_count": len(candidates)},
                    ):
                        results = self.reranker.rerank(
                            question=question,
                            documents=candidates,
                            top_k=top_k,
                        )
                    for item in results:
                        item["score"] = item.get("rerank_score")
                        item["evidence_signal_score"] = item.get("rerank_score")
                        item["final_score_type"] = "rerank_score"
                except Exception as exc:
                    if not self.reranker_fail_open:
                        raise
                    reranker_degraded = True
                    degraded = True
                    degraded_components.append("reranker")
                    reason = f"Reranker unavailable: {exc}"
                    degraded_reason = (
                        f"{degraded_reason}; {reason}"
                        if degraded_reason
                        else reason
                    )
                    results = candidates[:top_k]
                    log_business_event(
                        "reranker_degraded",
                        status="degraded",
                        error_message=str(exc),
                        degraded=True,
                        degraded_reason=reason,
                        retrieval_mode="hybrid_without_reranker",
                    )
                finally:
                    reranker_latency_ms = (
                        perf_counter() - reranker_started_at
                    ) * 1000
            else:
                results = candidates[:top_k]

            if self.neighbor_expansion_enabled and results:
                neighbor_started_at = perf_counter()
                try:
                    results, neighbor_added_count = self._expand_neighbors(
                        question,
                        results,
                        top_k=top_k,
                    )
                except KeywordSearchError as exc:
                    neighbor_expansion_degraded = True
                    neighbor_expansion_reason = str(exc)
                    log_business_event(
                        "neighbor_expansion_degraded",
                        status="degraded",
                        error_message=str(exc),
                        degraded=True,
                        degraded_reason=str(exc),
                        retrieval_mode="hybrid_without_neighbor_expansion",
                    )
                finally:
                    neighbor_expansion_latency_ms = (
                        perf_counter() - neighbor_started_at
                    ) * 1000

            total_latency_ms = (perf_counter() - started_at) * 1000
            retrieval_mode = "vector_only" if degraded else "hybrid"
            event = RetrievalUsageEvent(
                operation="document_retrieval",
                latency_ms=round(total_latency_ms, 2),
                top_k=top_k,
                vector_hit_count=len(vector_results),
                keyword_hit_count=len(keyword_results),
                fused_hit_count=len(merged),
                returned_count=len(results),
                reranker_used=(
                    self.use_reranker
                    and self.reranker is not None
                    and bool(candidates)
                ),
                retrieval_mode=retrieval_mode,
                degraded=degraded,
                degraded_reason=degraded_reason,
                qdrant_latency_ms=round(vector_latency_ms, 2),
                opensearch_latency_ms=round(keyword_latency_ms, 2),
                fusion_latency_ms=round(fusion_latency_ms, 2),
                reranker_latency_ms=round(reranker_latency_ms, 2),
                collection_name=getattr(
                    self.vector_backend,
                    "collection_alias",
                    getattr(self.vector_backend, "collection_name", None),
                ),
                keyword_index=getattr(self.keyword_backend, "index_name", None),
                embedding_index_version=getattr(
                    getattr(self.vector_backend, "embedding_provider", None),
                    "index_version",
                    None,
                ),
                metadata={
                    "query_hash": sha256(question.encode("utf-8")).hexdigest(),
                    "fusion_strategy": self.fusion_strategy,
                    "rerank_candidate_limit": rerank_candidate_k,
                    "rerank_candidate_count": len(candidates),
                    "neighbor_expansion_enabled": self.neighbor_expansion_enabled,
                    "neighbor_added_count": neighbor_added_count,
                    "neighbor_expansion_degraded": neighbor_expansion_degraded,
                    "neighbor_expansion_reason": neighbor_expansion_reason,
                    "neighbor_expansion_latency_ms": round(
                        neighbor_expansion_latency_ms,
                        2,
                    ),
                    "filters": (
                        retrieval_filter.as_dict() if retrieval_filter else {}
                    ),
                },
            )
            add_retrieval_usage_event(event)
            record_retrieval(
                retrieval_mode=retrieval_mode,
                status="success",
                latency_ms=total_latency_ms,
                degraded=degraded,
            )

            return {
                "contexts": results,
                "metadata": {
                    "degraded": degraded,
                    "degraded_reason": degraded_reason,
                    "retrieval_mode": retrieval_mode,
                    "fusion_strategy": self.fusion_strategy,
                    "filters_applied": (
                        retrieval_filter.as_dict() if retrieval_filter else {}
                    ),
                    "degraded_components": degraded_components,
                    "reranker_degraded": reranker_degraded,
                    "rerank_candidate_limit": rerank_candidate_k,
                    "rerank_candidate_count": len(candidates),
                    "vector_result_count": len(vector_results),
                    "keyword_result_count": len(keyword_results),
                    "qdrant_latency_ms": round(vector_latency_ms, 2),
                    "opensearch_latency_ms": round(keyword_latency_ms, 2),
                    "fusion_latency_ms": round(fusion_latency_ms, 2),
                    "reranker_latency_ms": round(reranker_latency_ms, 2),
                    "neighbor_expansion_latency_ms": round(
                        neighbor_expansion_latency_ms,
                        2,
                    ),
                    "neighbor_added_count": neighbor_added_count,
                    "neighbor_expansion_degraded": neighbor_expansion_degraded,
                    "neighbor_expansion_reason": neighbor_expansion_reason,
                },
            }
        except Exception as exc:
            total_latency_ms = (perf_counter() - started_at) * 1000
            retrieval_mode = "vector_only" if degraded else "hybrid"
            add_retrieval_usage_event(
                RetrievalUsageEvent(
                    operation="document_retrieval",
                    latency_ms=round(total_latency_ms, 2),
                    top_k=top_k,
                    vector_hit_count=len(vector_results),
                    keyword_hit_count=len(keyword_results),
                    fused_hit_count=len(merged),
                    retrieval_mode=retrieval_mode,
                    degraded=degraded,
                    degraded_reason=degraded_reason,
                    qdrant_latency_ms=round(vector_latency_ms, 2),
                    opensearch_latency_ms=round(keyword_latency_ms, 2),
                    fusion_latency_ms=round(fusion_latency_ms, 2),
                    reranker_latency_ms=round(reranker_latency_ms, 2),
                    embedding_index_version=getattr(
                        getattr(self.vector_backend, "embedding_provider", None),
                        "index_version",
                        None,
                    ),
                    status="failed",
                    error_type=type(exc).__name__,
                    metadata={
                        "query_hash": sha256(question.encode("utf-8")).hexdigest(),
                        "fusion_strategy": self.fusion_strategy,
                        "filters": (
                            retrieval_filter.as_dict()
                            if retrieval_filter
                            else {}
                        ),
                    },
                )
            )
            record_retrieval(
                retrieval_mode=retrieval_mode,
                status="failed",
                latency_ms=total_latency_ms,
                degraded=degraded,
            )
            raise

    def _expand_neighbors(
        self,
        question: str,
        results: list[dict],
        *,
        top_k: int,
    ) -> tuple[list[dict], int]:
        fetch_neighbors = getattr(
            self.keyword_backend,
            "get_adjacent_chunks",
            None,
        )
        if not callable(fetch_neighbors) or top_k <= 1:
            return results[:top_k], 0

        seed_pool_size = min(self.neighbor_seed_k, len(results))
        seeds = results[:seed_pool_size]
        neighbors = fetch_neighbors(seeds, window=self.neighbor_window)
        neighbor_slots = min(max(1, top_k // 2), max(0, top_k - 1))
        preserved_count = max(1, top_k - neighbor_slots)
        selected = list(results[:preserved_count])
        selected_ids = {
            str(item.get("chunk_id") or "")
            for item in selected
            if item.get("chunk_id")
        }
        added = 0

        ranked_seeds = sorted(
            enumerate(seeds),
            key=lambda pair: (
                -self._metadata_query_overlap(question, pair[1]),
                pair[0],
            ),
        )
        for _, seed in ranked_seeds:
            if added >= neighbor_slots:
                break
            seed_index = seed.get("chunk_index")
            if not isinstance(seed_index, int):
                continue
            matching = [
                item
                for item in neighbors
                if item.get("doc_id") == seed.get("doc_id")
                and isinstance(item.get("chunk_index"), int)
                and str(item.get("chunk_id") or "") not in selected_ids
            ]
            matching.sort(
                key=lambda item: (
                    0 if int(item["chunk_index"]) > seed_index else 1,
                    abs(int(item["chunk_index"]) - seed_index),
                )
            )
            for neighbor in matching[: self.neighbor_max_per_seed]:
                enriched = {
                    **neighbor,
                    "retrieval_source": "adjacent",
                    "adjacent_to_chunk_id": seed.get("chunk_id"),
                    "adjacent_distance": abs(
                        int(neighbor["chunk_index"]) - seed_index
                    ),
                    "score": float(seed.get("score") or 0.0) * 0.99,
                    "evidence_signal_score": float(
                        seed.get("evidence_signal_score")
                        or seed.get("score")
                        or 0.0
                    )
                    * 0.99,
                    "final_score_type": "adjacent_context",
                }
                selected.append(enriched)
                selected_ids.add(str(enriched.get("chunk_id") or ""))
                added += 1
                if added >= neighbor_slots:
                    break

        for item in results[preserved_count:]:
            chunk_id = str(item.get("chunk_id") or "")
            if chunk_id and chunk_id in selected_ids:
                continue
            selected.append(item)
            if chunk_id:
                selected_ids.add(chunk_id)
            if len(selected) >= top_k:
                break
        return selected[:top_k], min(added, neighbor_slots)

    @staticmethod
    def _metadata_query_overlap(question: str, item: dict[str, Any]) -> int:
        """Rank expansion seeds using transparent source/heading bigram overlap."""
        source = Path(str(item.get("source") or "")).stem
        heading = item.get("heading_path") or ""
        if isinstance(heading, (list, tuple)):
            heading = " ".join(str(value) for value in heading)
        metadata_text = f"{source} {heading}"

        def bigrams(value: str) -> set[str]:
            normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())
            if len(normalized) < 2:
                return {normalized} if normalized else set()
            return {
                normalized[index : index + 2]
                for index in range(len(normalized) - 1)
            }

        return len(bigrams(question) & bigrams(metadata_text))


@lru_cache(maxsize=1)
def build_online_hybrid_retriever() -> OnlineHybridRetriever:
    from app.core.config import settings

    provider = get_embedding_provider()
    vector_backend = QdrantVectorSearchBackend(
        provider,
        collection_name=settings.qdrant_collection,
        collection_alias=settings.qdrant_collection_alias,
    )

    backend_name = settings.keyword_search_backend.strip().lower()
    if backend_name != "opensearch":
        raise ValueError(f"Unsupported keyword search backend: {backend_name}")
    keyword_backend = OpenSearchKeywordBackend(
        index_name=(
            f"{settings.opensearch_index_prefix}_keyword_"
            f"{settings.keyword_index_version}"
        )
    )
    return OnlineHybridRetriever(
        vector_backend,
        keyword_backend,
        degraded_mode=settings.hybrid_degraded_mode,
        rrf_k=settings.retrieval_rrf_k,
        fusion_strategy=settings.retrieval_fusion_strategy,
        vector_weight=settings.retrieval_vector_weight,
        keyword_weight=settings.retrieval_keyword_weight,
        use_reranker=settings.use_reranker,
        reranker_fail_open=settings.reranker_fail_open,
        neighbor_expansion_enabled=settings.retrieval_neighbor_expansion_enabled,
        neighbor_seed_k=settings.retrieval_neighbor_seed_k,
        neighbor_window=settings.retrieval_neighbor_window,
        neighbor_max_per_seed=settings.retrieval_neighbor_max_per_seed,
    )


def clear_online_hybrid_retriever_cache() -> None:
    build_online_hybrid_retriever.cache_clear()
