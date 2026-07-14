from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from time import perf_counter
from typing import Any

from app.core.logger import log_business_event
from app.core.metrics import record_retrieval
from app.core.telemetry import traced_span
from app.core.telemetry_context import add_retrieval_usage_event
from app.observability.usage_models import RetrievalUsageEvent
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.fusion import reciprocal_rank_fusion
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
        use_reranker: bool = False,
        reranker: Any | None = None,
    ) -> None:
        if degraded_mode != "vector_only":
            raise ValueError(
                f"Unsupported HYBRID_DEGRADED_MODE: {degraded_mode}"
            )
        self.vector_backend = vector_backend
        self.keyword_backend = keyword_backend
        self.degraded_mode = degraded_mode
        self.rrf_k = rrf_k
        self.use_reranker = use_reranker
        self.reranker = reranker

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
    ) -> dict:
        started_at = perf_counter()
        vector_results: list[dict] = []
        keyword_results: list[dict] = []
        merged: list[dict] = []
        degraded = False
        degraded_reason = None
        vector_latency_ms = 0.0
        keyword_latency_ms = 0.0
        fusion_latency_ms = 0.0
        reranker_latency_ms = 0.0

        try:
            vector_started_at = perf_counter()
            with traced_span(
                "retrieval.qdrant_search",
                attributes={"rag.top_k": vector_top_k},
            ):
                vector_results = self.vector_backend.search(
                    question,
                    top_k=vector_top_k,
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
                    )
            except KeywordSearchError as exc:
                if self.degraded_mode != "vector_only":
                    raise
                degraded = True
                degraded_reason = str(exc)
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
                merged = reciprocal_rank_fusion(
                    vector_results,
                    keyword_results,
                    rrf_k=self.rrf_k,
                )
            fusion_latency_ms = (perf_counter() - fusion_started_at) * 1000
            candidates = merged[:rerank_candidate_k]

            if self.use_reranker and self.reranker is not None and candidates:
                reranker_started_at = perf_counter()
                with traced_span(
                    "retrieval.reranker",
                    attributes={"rag.candidate_count": len(candidates)},
                ):
                    results = self.reranker.rerank(
                        question=question,
                        documents=candidates,
                        top_k=top_k,
                    )
                reranker_latency_ms = (
                    perf_counter() - reranker_started_at
                ) * 1000
                for item in results:
                    item["score"] = item.get("rerank_score")
                    item["evidence_signal_score"] = item.get("rerank_score")
                    item["final_score_type"] = "rerank_score"
            else:
                results = candidates[:top_k]

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
                    "vector_result_count": len(vector_results),
                    "keyword_result_count": len(keyword_results),
                    "qdrant_latency_ms": round(vector_latency_ms, 2),
                    "opensearch_latency_ms": round(keyword_latency_ms, 2),
                    "fusion_latency_ms": round(fusion_latency_ms, 2),
                    "reranker_latency_ms": round(reranker_latency_ms, 2),
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
        use_reranker=settings.use_reranker,
    )


def clear_online_hybrid_retriever_cache() -> None:
    build_online_hybrid_retriever.cache_clear()
