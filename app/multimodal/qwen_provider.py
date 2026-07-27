from __future__ import annotations

from threading import Lock
from time import perf_counter
from typing import Any, Protocol

import requests

from app.core.logger import log_business_event
from app.core.telemetry import traced_span
from app.multimodal.base import (
    MultimodalEmbeddingDimensionError,
    MultimodalEmbeddingError,
)
from app.multimodal.types import MultimodalEmbeddingInput
from app.observability.model_usage import record_embedding_call


class QwenMultimodalEmbeddingProvider:
    """DashScope qwen3-vl-embedding adapter using one fused vector per item."""

    provider_name = "qwen"
    _DOCUMENT_INSTRUCT = (
        "Represent this industrial document asset for multimodal retrieval."
    )
    _QUERY_INSTRUCT = (
        "Represent this industrial quality search query for retrieving relevant assets."
    )

    def __init__(
        self,
        *,
        api_key: str | None,
        endpoint: str,
        model_name: str = "qwen3-vl-embedding",
        dimension: int = 1024,
        index_version: str = "qwen3vl-1024-v1",
        client: _HttpClient | None = None,
    ) -> None:
        if not api_key:
            raise MultimodalEmbeddingError(
                "QWEN_MULTIMODAL_EMBEDDING_API_KEY is required"
            )
        if dimension not in {2560, 2048, 1536, 1024, 768, 512, 256}:
            raise ValueError("unsupported qwen3-vl-embedding dimension")
        self.api_key = api_key
        self.endpoint = endpoint
        self.model_name = model_name
        self.dimension = dimension
        self.index_version = index_version
        self._client = client or _create_session(api_key)
        self._dimension_validated = False
        self._dimension_lock = Lock()

    @property
    def dimension_validated(self) -> bool:
        return self._dimension_validated

    def embed_documents(
        self,
        inputs: list[MultimodalEmbeddingInput],
    ) -> list[list[float]]:
        if not inputs:
            raise ValueError("multimodal document inputs cannot be empty")
        return [
            self._embed_one(value, operation="document") for value in inputs
        ]

    def embed_query(self, value: MultimodalEmbeddingInput) -> list[float]:
        return self._embed_one(value, operation="query")

    def _embed_one(
        self,
        value: MultimodalEmbeddingInput,
        *,
        operation: str,
    ) -> list[float]:
        started_at = perf_counter()
        contents = value.to_api_contents()
        payload = {
            "model": self.model_name,
            "input": {"contents": contents},
            "parameters": {
                "dimension": self.dimension,
                "output_type": "dense",
                "enable_fusion": True,
                "instruct": (
                    self._DOCUMENT_INSTRUCT
                    if operation == "document"
                    else self._QUERY_INSTRUCT
                ),
            },
        }
        operation_name = f"multimodal_embedding_{operation}"
        try:
            with traced_span(
                f"ai.{operation_name}",
                attributes={
                    "ai.provider": self.provider_name,
                    "ai.model": self.model_name,
                    "ai.operation": operation_name,
                    "ai.embedding.dimension": self.dimension,
                    "ai.modalities": ",".join(value.modalities),
                },
            ):
                response = self._client.post(
                    self.endpoint,
                    json=payload,
                    timeout=(10.0, 60.0),
                )
                response.raise_for_status()
                response_payload = response.json()
                vector = self._parse_fused_vector(response_payload)
                self._validate_dimension_once(vector)
            record_embedding_call(
                component="multimodal_embedding_provider",
                operation=operation_name,
                provider=self.provider_name,
                model_name=self.model_name,
                latency_ms=(perf_counter() - started_at) * 1000,
                input_text_count=int(bool(value.text)),
                input_char_count=len(value.text or ""),
                input_tokens=self._extract_input_tokens(response_payload),
                status="success",
                metadata={
                    "modalities": list(value.modalities),
                    "embedding_dimension": self.dimension,
                    "embedding_index_version": self.index_version,
                },
            )
            return vector
        except (
            MultimodalEmbeddingError,
            requests.RequestException,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            latency_ms = (perf_counter() - started_at) * 1000
            record_embedding_call(
                component="multimodal_embedding_provider",
                operation=operation_name,
                provider=self.provider_name,
                model_name=self.model_name,
                latency_ms=latency_ms,
                input_text_count=int(bool(value.text)),
                input_char_count=len(value.text or ""),
                input_tokens=None,
                status="failed",
                error_type=type(exc).__name__,
                metadata={
                    "modalities": list(value.modalities),
                    "embedding_dimension": self.dimension,
                    "embedding_index_version": self.index_version,
                },
            )
            log_business_event(
                "multimodal_embedding_request_failed",
                status="failed",
                error_message=str(exc),
                embedding_provider=self.provider_name,
                embedding_model=self.model_name,
                embedding_dimension=self.dimension,
                embedding_index_version=self.index_version,
                modalities=list(value.modalities),
            )
            if isinstance(exc, MultimodalEmbeddingError):
                raise
            raise MultimodalEmbeddingError(
                f"Qwen multimodal embedding request failed: {exc}"
            ) from exc

    @staticmethod
    def _parse_fused_vector(payload: dict[str, Any]) -> list[float]:
        embeddings = payload["output"]["embeddings"]
        if len(embeddings) != 1:
            raise MultimodalEmbeddingError(
                "fused embedding response must contain exactly one vector"
            )
        embedding_type = embeddings[0].get("type")
        if embedding_type not in {None, "fusion", "fused", "vl"}:
            raise MultimodalEmbeddingError(
                f"unexpected fused embedding response type: {embedding_type}"
            )
        return [float(value) for value in embeddings[0]["embedding"]]

    def _validate_dimension_once(self, vector: list[float]) -> None:
        if self._dimension_validated:
            return
        with self._dimension_lock:
            if self._dimension_validated:
                return
            if len(vector) != self.dimension:
                raise MultimodalEmbeddingDimensionError(
                    "Qwen multimodal embedding dimension mismatch: "
                    f"expected {self.dimension}, got {len(vector)}"
                )
            self._dimension_validated = True
            log_business_event(
                "multimodal_embedding_dimension_validated",
                embedding_provider=self.provider_name,
                embedding_model=self.model_name,
                embedding_dimension=self.dimension,
                embedding_index_version=self.index_version,
            )

    @staticmethod
    def _extract_input_tokens(payload: dict[str, Any]) -> int | None:
        usage = payload.get("usage") or payload.get("output", {}).get("usage") or {}
        value = usage.get("input_tokens", usage.get("total_tokens"))
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None


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
