from typing import Protocol, runtime_checkable


class EmbeddingProviderError(RuntimeError):
    """Base error raised by project embedding providers."""


class EmbeddingDimensionError(EmbeddingProviderError):
    """Raised before indexing when an embedding dimension is invalid."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int
    index_version: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed knowledge-base content using document semantics."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a search request using query semantics."""
