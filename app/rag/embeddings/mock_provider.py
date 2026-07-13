import hashlib
import math


class MockEmbeddingProvider:
    """Deterministic offline embeddings for unit and contract tests."""

    provider_name = "mock"

    def __init__(
        self,
        dimension: int = 8,
        model_name: str = "mock-embedding",
        index_version: str = "test-v1",
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than zero")
        self.dimension = dimension
        self.model_name = model_name
        self.index_version = index_version

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text, text_type="document") for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, text_type="query")

    def _embed(self, text: str, *, text_type: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("embedding input cannot be empty")

        seed = f"{text_type}:{text}".encode("utf-8")
        values: list[float] = []
        counter = 0
        while len(values) < self.dimension:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            values.extend((byte / 127.5) - 1.0 for byte in digest)
            counter += 1

        vector = values[: self.dimension]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
