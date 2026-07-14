from __future__ import annotations

from threading import Lock
from time import perf_counter
from typing import Any, Protocol

import requests

from app.core.logger import log_business_event
from app.rag.embeddings.base import (
    EmbeddingDimensionError,
    EmbeddingProviderError,
)
from app.core.telemetry import traced_span
from app.observability.model_usage import record_embedding_call


class QwenEmbeddingProvider:
    """DashScope native embedding adapter with asymmetric retrieval semantics."""

    provider_name = "qwen"

    def __init__(
        self,
        *,
        api_key: str | None,
        model_name: str = "text-embedding-v4",
        dimension: int = 1024,
        endpoint: str,
        batch_size: int = 10,
        index_version: str = "qwen-1024-v1",
        client: _HttpClient | None = None,
    ) -> None:
        if not api_key:
            raise EmbeddingProviderError(
                "QWEN_EMBEDDING_API_KEY is required for Qwen embeddings"
            )
        if dimension <= 0:
            raise ValueError("dimension must be greater than zero")
        if batch_size <= 0 or batch_size > 10:
            raise ValueError("batch_size must be between 1 and 10")

        self.api_key = api_key
        self.model_name = model_name
        self.dimension = dimension
        self.endpoint = endpoint
        self.batch_size = batch_size
        self.index_version = index_version
        self._client = client or _create_session(api_key)
        self._dimension_validated = False
        self._dimension_lock = Lock()

    @property
    def dimension_validated(self) -> bool:
        return self._dimension_validated

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, text_type="document")

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([text], text_type="query")
        return vectors[0]

    def _embed(self, texts: list[str], *, text_type: str) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned or any(not text for text in cleaned):
            raise ValueError("embedding input cannot be empty")

        vectors: list[list[float]] = []
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start : start + self.batch_size]
            vectors.extend(self._request_batch(batch, text_type=text_type))
        return vectors

    def _request_batch(
        self,
        texts: list[str],
        *,
        text_type: str,
    ) -> list[list[float]]:
        operation = f"embedding_{text_type}"
        started_at = perf_counter()
        payload = {
            "model": self.model_name,
            "input": {"texts": texts},
            "parameters": {
                "text_type": text_type,
                "dimension": self.dimension,
                "output_type": "dense",
            },
        }

        try:
            with traced_span(
                f"ai.{operation}",
                attributes={
                    "ai.provider": self.provider_name,
                    "ai.model": self.model_name,
                    "ai.operation": operation,
                    "ai.embedding.dimension": self.dimension,
                    "ai.input_text_count": len(texts),
                },
            ):
                response = self._client.post(
                    self.endpoint,
                    json=payload,
                    timeout=(10.0, 30.0),
                )
                response.raise_for_status()
                data = response.json()
                vectors = self._parse_vectors(data, expected_count=len(texts))
                self._validate_dimension_once(vectors)
            input_tokens = self._extract_input_tokens(data)
            record_embedding_call(
                component="embedding_provider",
                operation=operation,
                provider=self.provider_name,
                model_name=self.model_name,
                latency_ms=(perf_counter() - started_at) * 1000,
                input_text_count=len(texts),
                input_char_count=sum(len(text) for text in texts),
                input_tokens=input_tokens,
                status="success",
                metadata={
                    "embedding_dimension": self.dimension,
                    "embedding_index_version": self.index_version,
                },
            )
            return vectors
        except (
            EmbeddingProviderError,
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            record_embedding_call(
                component="embedding_provider",
                operation=operation,
                provider=self.provider_name,
                model_name=self.model_name,
                latency_ms=(perf_counter() - started_at) * 1000,
                input_text_count=len(texts),
                input_char_count=sum(len(text) for text in texts),
                input_tokens=None,
                status="failed",
                error_type=type(exc).__name__,
                metadata={
                    "embedding_dimension": self.dimension,
                    "embedding_index_version": self.index_version,
                },
            )
            log_business_event(
                "embedding_request_failed",
                status="failed",
                error_message=str(exc),
                embedding_provider=self.provider_name,
                embedding_model=self.model_name,
                embedding_dimension=self.dimension,
                embedding_index_version=self.index_version,
                text_type=text_type,
            )
            if isinstance(exc, EmbeddingProviderError):
                raise
            raise EmbeddingProviderError(
                f"Qwen embedding request failed: {exc}"
            ) from exc

    @staticmethod
    def _extract_input_tokens(payload: dict[str, Any]) -> int | None:
        usage = payload.get("usage") or payload.get("output", {}).get("usage") or {}
        if not isinstance(usage, dict):
            return None
        value = usage.get("input_tokens", usage.get("total_tokens"))
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _parse_vectors(
        self,
        payload: dict[str, Any],
        *,
        expected_count: int,
    ) -> list[list[float]]:
        embeddings = payload["output"]["embeddings"]
        ordered = sorted(
            embeddings,
            key=lambda item: int(item.get("text_index", item.get("index", 0))),
        )
        vectors = [list(item["embedding"]) for item in ordered]
        if len(vectors) != expected_count:
            raise EmbeddingProviderError(
                "Qwen embedding response count mismatch: "
                f"expected {expected_count}, got {len(vectors)}"
            )
        return vectors

    def _validate_dimension_once(self, vectors: list[list[float]]) -> None:
        if self._dimension_validated:
            return

        with self._dimension_lock:
            if self._dimension_validated:
                return
            actual_dimensions = {len(vector) for vector in vectors}
            if actual_dimensions != {self.dimension}:
                actual = sorted(actual_dimensions)
                raise EmbeddingDimensionError(
                    "Qwen embedding dimension mismatch: "
                    f"expected {self.dimension}, got {actual}"
                )
            self._dimension_validated = True
            log_business_event(
                "embedding_dimension_validated",
                embedding_provider=self.provider_name,
                embedding_model=self.model_name,
                embedding_dimension=self.dimension,
                embedding_index_version=self.index_version,
            )


class _HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, Any]: ...


class _HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: tuple[float, float],
    ) -> _HttpResponse: ...


def _create_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    )
    return session
