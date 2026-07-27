from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.core.logger import log_business_event
from app.multimodal.base import (
    MultimodalEmbeddingDimensionError,
    MultimodalEmbeddingProvider,
)
from app.multimodal.types import MultimodalEmbeddingInput
from app.rag.qdrant_client import get_qdrant_client
from app.rag.retrieval_filters import RetrievalFilter
from app.rag.search_backends.base import VectorSearchError


class MultimodalQdrantSearchBackend:
    """Isolated Qdrant backend for unified text/image vectors."""

    def __init__(
        self,
        embedding_provider: MultimodalEmbeddingProvider,
        *,
        collection_name: str,
        collection_alias: str,
        client: Any | None = None,
        models_module: Any | None = None,
    ) -> None:
        if not collection_name or not collection_alias:
            raise ValueError("multimodal collection and alias are required")
        if collection_name == collection_alias:
            raise ValueError("multimodal collection and alias must differ")
        self.embedding_provider = embedding_provider
        self.collection_name = collection_name
        self.collection_alias = collection_alias
        self.client = client or get_qdrant_client()
        self._models_module = models_module

    @property
    def models(self) -> Any:
        if self._models_module is None:
            from qdrant_client import models

            self._models_module = models
        return self._models_module

    def ensure_index(self) -> None:
        try:
            if self.client.collection_exists(self.collection_name):
                self._validate_existing_dimension()
                return
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=self.models.VectorParams(
                    size=self.embedding_provider.dimension,
                    distance=self.models.Distance.COSINE,
                ),
            )
        except MultimodalEmbeddingDimensionError:
            raise
        except Exception as exc:
            raise VectorSearchError(
                f"Unable to ensure multimodal Qdrant collection: {exc}"
            ) from exc

    def upsert_document_assets(
        self,
        doc_id: str,
        assets: list[dict],
        *,
        index_status: str = "indexed",
        index_operation_id: str | None = None,
    ) -> None:
        if not assets:
            return
        try:
            self.ensure_index()
            inputs = [self._input_from_asset(asset) for asset in assets]
            vectors = self.embedding_provider.embed_documents(inputs)
            self._validate_vectors(vectors, expected_count=len(assets))
            points = []
            for index, (asset, vector) in enumerate(zip(assets, vectors)):
                metadata = asset.get("metadata", {})
                asset_id = metadata.get("asset_id") or f"{doc_id}_asset_{index}"
                point_id = str(uuid5(NAMESPACE_URL, f"{doc_id}:{asset_id}"))
                points.append(
                    self.models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "doc_id": doc_id,
                            "asset_id": asset_id,
                            "chunk_id": metadata.get("chunk_id"),
                            "page_number": metadata.get("page_number"),
                            "modality": metadata.get(
                                "modality",
                                "+".join(inputs[index].modalities),
                            ),
                            "text": asset.get("text", ""),
                            "source": metadata.get("source"),
                            "doc_type": metadata.get("doc_type"),
                            "version": metadata.get("version"),
                            "asset_path": metadata.get("asset_path"),
                            "preview_url": metadata.get("preview_url"),
                            "index_status": index_status,
                            "index_operation_id": index_operation_id,
                            "embedding_provider": self.embedding_provider.provider_name,
                            "embedding_model": self.embedding_provider.model_name,
                            "embedding_dimension": self.embedding_provider.dimension,
                            "embedding_index_version": (
                                self.embedding_provider.index_version
                            ),
                        },
                    )
                )
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        except (MultimodalEmbeddingDimensionError, VectorSearchError):
            raise
        except Exception as exc:
            raise VectorSearchError(
                f"Unable to index multimodal assets for {doc_id}: {exc}"
            ) from exc

    def delete_by_doc_id(
        self,
        doc_id: str,
        *,
        index_operation_id: str | None = None,
        exclude_operation_id: str | None = None,
    ) -> None:
        try:
            if not self.client.collection_exists(self.collection_name):
                return
            conditions = [
                self.models.FieldCondition(
                    key="doc_id",
                    match=self.models.MatchValue(value=doc_id),
                )
            ]
            if index_operation_id:
                conditions.append(
                    self.models.FieldCondition(
                        key="index_operation_id",
                        match=self.models.MatchValue(value=index_operation_id),
                    )
                )
            excluded_conditions = []
            if exclude_operation_id:
                excluded_conditions.append(
                    self.models.FieldCondition(
                        key="index_operation_id",
                        match=self.models.MatchValue(value=exclude_operation_id),
                    )
                )
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=self.models.FilterSelector(
                    filter=self.models.Filter(
                        must=conditions,
                        must_not=excluded_conditions or None,
                    )
                ),
                wait=True,
            )
        except Exception as exc:
            raise VectorSearchError(
                f"Unable to delete multimodal assets for {doc_id}: {exc}"
            ) from exc

    def set_document_index_status(
        self,
        doc_id: str,
        status: str,
        *,
        index_operation_id: str,
    ) -> None:
        try:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload={"index_status": status},
                points=self.models.Filter(
                    must=[
                        self.models.FieldCondition(
                            key="doc_id",
                            match=self.models.MatchValue(value=doc_id),
                        ),
                        self.models.FieldCondition(
                            key="index_operation_id",
                            match=self.models.MatchValue(
                                value=index_operation_id
                            ),
                        ),
                    ]
                ),
                wait=True,
            )
        except Exception as exc:
            raise VectorSearchError(
                f"Unable to update multimodal status for {doc_id}: {exc}"
            ) from exc

    def count_indexed(self) -> int:
        try:
            if not self.client.collection_exists(self.collection_name):
                return 0
            result = self.client.count(
                collection_name=self.collection_name,
                count_filter=self.models.Filter(
                    must=[
                        self.models.FieldCondition(
                            key="index_status",
                            match=self.models.MatchValue(value="indexed"),
                        )
                    ]
                ),
                exact=True,
            )
            return int(result.count)
        except Exception as exc:
            raise VectorSearchError(
                f"Unable to count indexed multimodal points: {exc}"
            ) from exc

    def activate_alias(self) -> None:
        """Switch the stable alias only after a non-empty index is validated."""

        try:
            if not self.client.collection_exists(self.collection_name):
                raise VectorSearchError(
                    f"Cannot activate missing collection {self.collection_name}"
                )
            self._validate_existing_dimension()
            if self.count_indexed() <= 0:
                raise VectorSearchError(
                    "Cannot activate alias for an empty multimodal index"
                )
            existing = self.get_alias_target()
            if existing == self.collection_name:
                return
            actions = []
            if existing:
                actions.append(
                    self.models.DeleteAliasOperation(
                        delete_alias=self.models.DeleteAlias(
                            alias_name=self.collection_alias
                        )
                    )
                )
            actions.append(
                self.models.CreateAliasOperation(
                    create_alias=self.models.CreateAlias(
                        collection_name=self.collection_name,
                        alias_name=self.collection_alias,
                    )
                )
            )
            self.client.update_collection_aliases(
                change_aliases_operations=actions
            )
            log_business_event(
                "multimodal_qdrant_alias_activated",
                qdrant_collection=self.collection_name,
                qdrant_collection_alias=self.collection_alias,
                previous_collection=existing,
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=self.embedding_provider.dimension,
                embedding_index_version=self.embedding_provider.index_version,
            )
        except VectorSearchError:
            raise
        except Exception as exc:
            raise VectorSearchError(
                f"Unable to activate multimodal alias {self.collection_alias}: {exc}"
            ) from exc

    def get_alias_target(self) -> str | None:
        aliases = self.client.get_aliases().aliases
        for alias in aliases:
            if alias.alias_name == self.collection_alias:
                return alias.collection_name
        return None

    def search(
        self,
        query: MultimodalEmbeddingInput,
        top_k: int = 5,
        *,
        filters: RetrievalFilter | None = None,
    ) -> list[dict]:
        try:
            vector = self.embedding_provider.embed_query(query)
            self._validate_vectors([vector], expected_count=1)
            response = self.client.query_points(
                collection_name=self.collection_alias,
                query=vector,
                query_filter=self._build_search_filter(filters),
                limit=top_k,
                with_payload=True,
            )
            return [self._to_result(point) for point in response.points]
        except MultimodalEmbeddingDimensionError:
            raise
        except Exception as exc:
            raise VectorSearchError(
                f"Multimodal Qdrant search failed: {exc}"
            ) from exc

    def _build_search_filter(self, filters: RetrievalFilter | None) -> Any:
        conditions = [
            self.models.FieldCondition(
                key="index_status",
                match=self.models.MatchValue(value="indexed"),
            )
        ]
        if filters:
            for key, values in (
                ("doc_id", filters.doc_ids),
                ("doc_type", filters.doc_types),
                ("version", filters.versions),
                ("source", filters.sources),
            ):
                if values:
                    conditions.append(
                        self.models.FieldCondition(
                            key=key,
                            match=self.models.MatchAny(any=list(values)),
                        )
                    )
        return self.models.Filter(must=conditions)

    @staticmethod
    def _input_from_asset(asset: dict) -> MultimodalEmbeddingInput:
        value = asset.get("embedding_input")
        if not isinstance(value, MultimodalEmbeddingInput):
            raise ValueError(
                "asset.embedding_input must be MultimodalEmbeddingInput"
            )
        return value

    def _validate_existing_dimension(self) -> None:
        info = self.client.get_collection(self.collection_name)
        vectors_config = info.config.params.vectors
        size = getattr(vectors_config, "size", None)
        if size is None and isinstance(vectors_config, dict):
            size = vectors_config.get("size")
        if size != self.embedding_provider.dimension:
            raise MultimodalEmbeddingDimensionError(
                f"Multimodal Qdrant dimension mismatch: expected "
                f"{self.embedding_provider.dimension}, got {size}"
            )

    def _validate_vectors(
        self,
        vectors: list[list[float]],
        *,
        expected_count: int,
    ) -> None:
        if len(vectors) != expected_count:
            raise MultimodalEmbeddingDimensionError(
                f"Embedding count mismatch: expected {expected_count}, got {len(vectors)}"
            )
        dimensions = {len(vector) for vector in vectors}
        if dimensions != {self.embedding_provider.dimension}:
            raise MultimodalEmbeddingDimensionError(
                "Multimodal vector dimension mismatch before Qdrant access: "
                f"expected {self.embedding_provider.dimension}, got {sorted(dimensions)}"
            )

    @staticmethod
    def _to_result(point: Any) -> dict:
        payload = point.payload or {}
        return {
            "text": payload.get("text", ""),
            "source": payload.get("source", ""),
            "doc_type": payload.get("doc_type", ""),
            "doc_id": payload.get("doc_id", ""),
            "chunk_id": payload.get("chunk_id", ""),
            "asset_id": payload.get("asset_id", ""),
            "asset_path": payload.get("asset_path"),
            "preview_url": payload.get("preview_url"),
            "page_number": payload.get("page_number"),
            "modality": payload.get("modality", ""),
            "version": payload.get("version", ""),
            "score": float(point.score),
            "retrieval_source": "multimodal_vector",
        }
