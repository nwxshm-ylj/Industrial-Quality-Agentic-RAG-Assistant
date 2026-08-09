from __future__ import annotations

from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Protocol

from app.core.logger import log_business_event
from app.core.telemetry import traced_span
from app.observability.model_usage import record_embedding_call
from app.rag.embeddings.base import (
    EmbeddingDimensionError,
    EmbeddingProviderError,
)


class LocalSentenceTransformerEmbeddingProvider:
    """Process-reused dense embedding provider backed by a local model."""

    provider_name = "local"

    def __init__(
        self,
        *,
        model_path: str | Path,
        model_name: str = "BAAI/bge-m3",
        model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181",
        dimension: int = 1024,
        batch_size: int = 8,
        device: str = "cpu",
        normalize_embeddings: bool = True,
        index_version: str = "bge-m3-1024-v1",
        model: "_SentenceTransformerModel | None" = None,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than zero")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        self.model_path = Path(model_path)
        self.model_name = model_name
        self.model_revision = model_revision
        self.dimension = dimension
        self.batch_size = batch_size
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self.index_version = index_version
        self._encode_lock = Lock()

        if model is None:
            if not self.model_path.is_dir():
                raise EmbeddingProviderError(
                    f"Local embedding model directory does not exist: {self.model_path}"
                )
            try:
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(
                    str(self.model_path.resolve()),
                    device=self.device,
                )
            except Exception as exc:
                raise EmbeddingProviderError(
                    f"Unable to load local embedding model: {exc}"
                ) from exc
        self._model = model
        self._validate_model_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, operation="embedding_document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], operation="embedding_query")[0]

    def _embed(self, texts: list[str], *, operation: str) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned or any(not text for text in cleaned):
            raise ValueError("embedding input cannot be empty")

        started_at = perf_counter()
        try:
            with traced_span(
                f"ai.{operation}",
                attributes={
                    "ai.provider": self.provider_name,
                    "ai.model": self.model_name,
                    "ai.operation": operation,
                    "ai.embedding.dimension": self.dimension,
                    "ai.input_text_count": len(cleaned),
                },
            ):
                # SentenceTransformer and its tokenizer share mutable state.
                # Serialize encode calls while reusing one loaded model instance.
                with self._encode_lock:
                    encoded = self._model.encode(
                        cleaned,
                        batch_size=self.batch_size,
                        normalize_embeddings=self.normalize_embeddings,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                    )
                vectors = _to_vectors(encoded)
                self._validate_vectors(vectors, expected_count=len(cleaned))
            record_embedding_call(
                component="embedding_provider",
                operation=operation,
                provider=self.provider_name,
                model_name=self.model_name,
                latency_ms=(perf_counter() - started_at) * 1000,
                input_text_count=len(cleaned),
                input_char_count=sum(len(text) for text in cleaned),
                input_tokens=None,
                status="success",
                metadata=self._usage_metadata(),
            )
            return vectors
        except (EmbeddingProviderError, ValueError, TypeError) as exc:
            self._record_failure(operation, cleaned, started_at, exc)
            if isinstance(exc, EmbeddingProviderError):
                raise
            raise EmbeddingProviderError(
                f"Local embedding inference failed: {exc}"
            ) from exc
        except Exception as exc:
            self._record_failure(operation, cleaned, started_at, exc)
            raise EmbeddingProviderError(
                f"Local embedding inference failed: {exc}"
            ) from exc

    def _validate_model_dimension(self) -> None:
        try:
            dimension_reader = getattr(
                self._model,
                "get_embedding_dimension",
                None,
            )
            if not callable(dimension_reader):
                dimension_reader = self._model.get_sentence_embedding_dimension
            actual = int(dimension_reader())
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Unable to read local embedding dimension: {exc}"
            ) from exc
        if actual != self.dimension:
            raise EmbeddingDimensionError(
                "Local embedding model dimension mismatch: "
                f"expected {self.dimension}, got {actual}"
            )
        log_business_event(
            "embedding_dimension_validated",
            embedding_provider=self.provider_name,
            embedding_model=self.model_name,
            embedding_dimension=self.dimension,
            embedding_index_version=self.index_version,
            embedding_model_revision=self.model_revision,
        )

    def _validate_vectors(
        self,
        vectors: list[list[float]],
        *,
        expected_count: int,
    ) -> None:
        if len(vectors) != expected_count:
            raise EmbeddingDimensionError(
                f"Embedding count mismatch: expected {expected_count}, got {len(vectors)}"
            )
        dimensions = {len(vector) for vector in vectors}
        if dimensions != {self.dimension}:
            raise EmbeddingDimensionError(
                "Local embedding output dimension mismatch: "
                f"expected {self.dimension}, got {sorted(dimensions)}"
            )

    def _usage_metadata(self) -> dict[str, Any]:
        return {
            "embedding_dimension": self.dimension,
            "embedding_index_version": self.index_version,
            "embedding_model_revision": self.model_revision,
            "embedding_device": self.device,
        }

    def _record_failure(
        self,
        operation: str,
        texts: list[str],
        started_at: float,
        error: Exception,
    ) -> None:
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
            error_type=type(error).__name__,
            metadata=self._usage_metadata(),
        )
        log_business_event(
            "embedding_inference_failed",
            status="failed",
            error_message=str(error),
            embedding_provider=self.provider_name,
            embedding_model=self.model_name,
            embedding_dimension=self.dimension,
            embedding_index_version=self.index_version,
            embedding_model_revision=self.model_revision,
            operation=operation,
        )


class _SentenceTransformerModel(Protocol):
    def get_embedding_dimension(self) -> int: ...

    def get_sentence_embedding_dimension(self) -> int: ...

    def encode(self, sentences: list[str], **kwargs: Any) -> Any: ...


def _to_vectors(value: Any) -> list[list[float]]:
    converted = value.tolist() if hasattr(value, "tolist") else value
    if not isinstance(converted, (list, tuple)):
        raise TypeError("Local embedding model returned a non-sequence")
    vectors: list[list[float]] = []
    for vector in converted:
        current = vector.tolist() if hasattr(vector, "tolist") else vector
        if not isinstance(current, (list, tuple)):
            raise TypeError("Local embedding vector is not a sequence")
        vectors.append([float(item) for item in current])
    return vectors
