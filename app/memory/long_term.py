from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.core.logger import log_business_event
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.opensearch_client import get_opensearch_client
from app.rag.qdrant_client import get_qdrant_client


class LongTermMemoryError(RuntimeError):
    pass


class LongTermMemoryStore(Protocol):
    def save_interaction(
        self,
        *,
        owner_key: str,
        session_id: str,
        question: str,
        answer: str,
        intent: str | None,
    ) -> str: ...

    def search(
        self,
        *,
        owner_key: str,
        query: str,
        limit: int,
    ) -> list[dict]: ...


class HybridLongTermMemoryStore:
    """Owner-isolated semantic + full-text episodic memory index."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        *,
        qdrant_client: Any,
        opensearch_client: Any,
        collection_name: str,
        index_name: str,
        semantic_score_threshold: float = 0.45,
        keyword_min_score: float = 0.0,
        models_module: Any | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.qdrant = qdrant_client
        self.opensearch = opensearch_client
        self.collection_name = collection_name
        self.index_name = index_name
        self.semantic_score_threshold = semantic_score_threshold
        self.keyword_min_score = keyword_min_score
        self._models_module = models_module

    @property
    def models(self) -> Any:
        if self._models_module is None:
            from qdrant_client import models

            self._models_module = models
        return self._models_module

    def ensure_indexes(self) -> None:
        if not self.qdrant.collection_exists(self.collection_name):
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=self.models.VectorParams(
                    size=self.embedding_provider.dimension,
                    distance=self.models.Distance.COSINE,
                ),
            )
        else:
            info = self.qdrant.get_collection(self.collection_name)
            vectors_config = info.config.params.vectors
            size = getattr(vectors_config, "size", None)
            if size is None and isinstance(vectors_config, dict):
                size = vectors_config.get("size")
            if size != self.embedding_provider.dimension:
                raise LongTermMemoryError(
                    "long-term memory vector dimension mismatch: "
                    f"expected {self.embedding_provider.dimension}, got {size}"
                )
        if not self.opensearch.indices.exists(index=self.index_name):
            self.opensearch.indices.create(
                index=self.index_name,
                body={
                    "mappings": {
                        "properties": {
                            "memory_id": {"type": "keyword"},
                            "owner_key": {"type": "keyword"},
                            "session_id": {"type": "keyword"},
                            "question": {"type": "text"},
                            "answer": {"type": "text"},
                            "content": {"type": "text"},
                            "intent": {"type": "keyword"},
                        }
                    }
                },
            )

    def save_interaction(
        self,
        *,
        owner_key: str,
        session_id: str,
        question: str,
        answer: str,
        intent: str | None,
    ) -> str:
        memory_id = uuid4().hex
        content = self._format_content(question, answer, intent)
        try:
            self.ensure_indexes()
            vector = self.embedding_provider.embed_documents([content])[0]
            if len(vector) != self.embedding_provider.dimension:
                raise LongTermMemoryError("long-term memory vector dimension mismatch")
            point_id = str(uuid5(NAMESPACE_URL, f"memory:{memory_id}"))
            payload = {
                "memory_id": memory_id,
                "owner_key": owner_key,
                "session_id": session_id,
                "question": question,
                "answer": answer,
                "content": content,
                "intent": intent,
                "embedding_provider": self.embedding_provider.provider_name,
                "embedding_model": self.embedding_provider.model_name,
                "embedding_dimension": self.embedding_provider.dimension,
                "embedding_index_version": self.embedding_provider.index_version,
            }
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[
                    self.models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
                wait=True,
            )
            try:
                self.opensearch.index(
                    index=self.index_name,
                    id=memory_id,
                    body=payload,
                    refresh=False,
                )
            except Exception:
                self.qdrant.delete(
                    collection_name=self.collection_name,
                    points_selector=self.models.PointIdsList(points=[point_id]),
                    wait=True,
                )
                raise
            return memory_id
        except Exception as exc:
            raise LongTermMemoryError(
                f"long-term memory indexing failed: {exc}"
            ) from exc

    def search(
        self,
        *,
        owner_key: str,
        query: str,
        limit: int,
    ) -> list[dict]:
        if not query.strip() or limit <= 0:
            return []
        vector_results: list[dict] = []
        keyword_results: list[dict] = []
        errors = []
        try:
            vector = self.embedding_provider.embed_query(query)
            response = self.qdrant.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=self.models.Filter(
                    must=[
                        self.models.FieldCondition(
                            key="owner_key",
                            match=self.models.MatchValue(value=owner_key),
                        )
                    ]
                ),
                score_threshold=self.semantic_score_threshold,
                limit=max(limit * 3, 10),
                with_payload=True,
            )
            vector_results = [
                self._qdrant_result(point) for point in response.points
            ]
        except Exception as exc:
            errors.append(f"qdrant={exc}")
        try:
            response = self.opensearch.search(
                index=self.index_name,
                body={
                    "size": max(limit * 3, 10),
                    "min_score": self.keyword_min_score,
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["question^2", "answer", "content"],
                                    }
                                }
                            ],
                            "filter": [{"term": {"owner_key": owner_key}}],
                        }
                    },
                },
            )
            keyword_results = [
                self._opensearch_result(hit)
                for hit in response.get("hits", {}).get("hits", [])
            ]
        except Exception as exc:
            errors.append(f"opensearch={exc}")
        if not vector_results and not keyword_results and len(errors) == 2:
            raise LongTermMemoryError("; ".join(errors))
        return reciprocal_rank_fusion(
            vector_results,
            keyword_results,
        )[:limit]

    @staticmethod
    def _format_content(question: str, answer: str, intent: str | None) -> str:
        return f"Intent: {intent or 'unknown'}\nQuestion: {question}\nAnswer: {answer}"

    @staticmethod
    def _qdrant_result(point: Any) -> dict:
        payload = point.payload or {}
        return {
            **payload,
            "chunk_id": payload.get("memory_id"),
            "text": payload.get("content", ""),
            "source": "long_term_memory",
            "score": float(point.score),
        }

    @staticmethod
    def _opensearch_result(hit: dict) -> dict:
        source = hit.get("_source", {})
        return {
            **source,
            "chunk_id": source.get("memory_id"),
            "text": source.get("content", ""),
            "source": "long_term_memory",
            "score": float(hit.get("_score", 0.0)),
        }


@lru_cache(maxsize=1)
def get_long_term_memory_store() -> HybridLongTermMemoryStore:
    from app.core.config import settings

    return HybridLongTermMemoryStore(
        get_embedding_provider(),
        qdrant_client=get_qdrant_client(),
        opensearch_client=get_opensearch_client(),
        collection_name=settings.memory_qdrant_collection,
        index_name=(
            f"{settings.opensearch_index_prefix}_memory_"
            f"{settings.memory_index_version}"
        ),
        semantic_score_threshold=settings.memory_semantic_score_threshold,
        keyword_min_score=settings.memory_keyword_min_score,
    )
