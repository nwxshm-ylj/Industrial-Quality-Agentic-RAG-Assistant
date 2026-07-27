from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.multimodal.types import MultimodalEmbeddingInput


class MultimodalEmbeddingError(RuntimeError):
    """Base error for project-owned multimodal embedding adapters."""


class MultimodalEmbeddingDimensionError(MultimodalEmbeddingError):
    """Raised before Qdrant access when a vector dimension is invalid."""


@runtime_checkable
class MultimodalEmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int
    index_version: str

    def embed_documents(
        self,
        inputs: list[MultimodalEmbeddingInput],
    ) -> list[list[float]]:
        """Embed stored assets with document-retrieval semantics."""

    def embed_query(self, value: MultimodalEmbeddingInput) -> list[float]:
        """Embed a text/image query with query-retrieval semantics."""
