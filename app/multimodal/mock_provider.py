from __future__ import annotations

from hashlib import sha256

from app.multimodal.types import MultimodalEmbeddingInput


class MockMultimodalEmbeddingProvider:
    """Deterministic, offline provider for unit tests."""

    provider_name = "mock"

    def __init__(
        self,
        *,
        dimension: int = 8,
        model_name: str = "mock-qwen3-vl-embedding",
        index_version: str = "mock-multimodal-v1",
    ) -> None:
        self.dimension = dimension
        self.model_name = model_name
        self.index_version = index_version

    def embed_documents(
        self,
        inputs: list[MultimodalEmbeddingInput],
    ) -> list[list[float]]:
        return [self._vector(value, "document") for value in inputs]

    def embed_query(self, value: MultimodalEmbeddingInput) -> list[float]:
        return self._vector(value, "query")

    def _vector(
        self,
        value: MultimodalEmbeddingInput,
        semantic_type: str,
    ) -> list[float]:
        raw = "|".join(
            [
                semantic_type,
                value.text or "",
                *value.images,
                value.video or "",
            ]
        ).encode("utf-8")
        seed = sha256(raw).digest()
        return [
            (seed[index % len(seed)] / 127.5) - 1.0
            for index in range(self.dimension)
        ]
