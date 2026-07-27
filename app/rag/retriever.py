from __future__ import annotations

from functools import lru_cache

from app.core.logger import log_business_event
from app.multimodal.factory import get_multimodal_embedding_provider
from app.multimodal.types import MultimodalEmbeddingInput
from app.rag.fusion import multimodal_rrf_fusion
from app.rag.online_hybrid_retriever import (
    OnlineHybridRetriever,
    build_online_hybrid_retriever,
)
from app.rag.retrieval_filters import RetrievalFilter
from app.rag.search_backends.base import VectorSearchError
from app.rag.search_backends.multimodal_qdrant_backend import (
    MultimodalQdrantSearchBackend,
)


@lru_cache(maxsize=1)
def build_multimodal_retriever() -> MultimodalQdrantSearchBackend:
    from app.core.config import settings

    return MultimodalQdrantSearchBackend(
        get_multimodal_embedding_provider(),
        collection_name=settings.qdrant_multimodal_collection,
        collection_alias=settings.qdrant_multimodal_collection_alias,
    )


class IndustrialRetriever:
    def __init__(
        self,
        hybrid_retriever: OnlineHybridRetriever | None = None,
        multimodal_retriever: MultimodalQdrantSearchBackend | None = None,
        multimodal_enabled: bool | None = None,
        multimodal_rrf_k: int | None = None,
        multimodal_degraded_mode: str | None = None,
    ):
        self.hybrid_retriever = (
            hybrid_retriever or build_online_hybrid_retriever()
        )
        self._multimodal_retriever = multimodal_retriever
        if (
            multimodal_enabled is None
            or multimodal_rrf_k is None
            or multimodal_degraded_mode is None
        ):
            from app.core.config import settings

        self.multimodal_enabled = (
            settings.multimodal_enabled
            if multimodal_enabled is None
            else multimodal_enabled
        )
        self.multimodal_rrf_k = (
            settings.retrieval_rrf_k
            if multimodal_rrf_k is None
            else multimodal_rrf_k
        )
        self.multimodal_degraded_mode = (
            settings.multimodal_degraded_mode
            if multimodal_degraded_mode is None
            else multimodal_degraded_mode
        )

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        filters: dict | None = None,
        multimodal_query: dict | None = None,
    ) -> list[dict]:
        return self.retrieve_with_metadata(
            question,
            top_k,
            filters,
            multimodal_query,
        )["contexts"]

    def retrieve_with_metadata(
        self,
        question: str,
        top_k: int = 5,
        filters: dict | None = None,
        multimodal_query: dict | None = None,
    ) -> dict:
        text_result = self.hybrid_retriever.retrieve(
            question=question,
            top_k=top_k,
            vector_top_k=max(top_k * 4, 20),
            keyword_top_k=max(top_k * 4, 20),
            rerank_candidate_k=max(top_k * 4, 20),
            filters=filters,
        )
        if not multimodal_query:
            return text_result
        if not self.multimodal_enabled:
            metadata = dict(text_result.get("metadata", {}))
            metadata.update(
                {
                    "multimodal_requested": True,
                    "multimodal_degraded": True,
                    "multimodal_degraded_reason": "MULTIMODAL_ENABLED is false",
                }
            )
            return {"contexts": text_result["contexts"], "metadata": metadata}

        images = tuple(multimodal_query.get("images") or ())
        video = multimodal_query.get("video")
        query_input = MultimodalEmbeddingInput(
            text=question,
            images=images,
            video=video,
        )
        try:
            backend = self._multimodal_retriever or build_multimodal_retriever()
            multimodal_results = backend.search(
                query_input,
                top_k=max(top_k * 4, 20),
                filters=RetrievalFilter.from_mapping(filters),
            )
            contexts = multimodal_rrf_fusion(
                text_result["contexts"],
                multimodal_results,
                rrf_k=self.multimodal_rrf_k,
            )[:top_k]
            metadata = dict(text_result.get("metadata", {}))
            metadata.update(
                {
                    "multimodal_requested": True,
                    "multimodal_degraded": False,
                    "multimodal_result_count": len(multimodal_results),
                    "multimodal_collection": getattr(
                        backend,
                        "collection_alias",
                        None,
                    ),
                    "cross_modal_fusion_strategy": "rrf",
                }
            )
            return {"contexts": contexts, "metadata": metadata}
        except VectorSearchError as exc:
            if self.multimodal_degraded_mode != "text_only":
                raise
            reason = str(exc)
            log_business_event(
                "multimodal_search_degraded",
                status="degraded",
                degraded=True,
                degraded_reason=reason,
                error_message=reason,
            )
            metadata = dict(text_result.get("metadata", {}))
            metadata.update(
                {
                    "multimodal_requested": True,
                    "multimodal_degraded": True,
                    "multimodal_degraded_reason": reason,
                }
            )
            return {"contexts": text_result["contexts"], "metadata": metadata}
