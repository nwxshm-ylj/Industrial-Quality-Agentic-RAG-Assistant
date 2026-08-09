from __future__ import annotations

from functools import lru_cache

from app.rag.embeddings.base import EmbeddingProvider


_testing_provider: EmbeddingProvider | None = None


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """Return one process-level provider instance."""

    if _testing_provider is not None:
        return _testing_provider

    from app.core.config import settings

    provider_name = settings.embedding_provider.strip().lower()
    if provider_name == "qwen":
        from app.rag.embeddings.qwen_provider import QwenEmbeddingProvider

        return QwenEmbeddingProvider(
            api_key=settings.qwen_embedding_api_key,
            model_name=settings.qwen_embedding_model,
            dimension=settings.qwen_embedding_dimension,
            endpoint=settings.qwen_embedding_base_url,
            batch_size=settings.qwen_embedding_batch_size,
            index_version=settings.embedding_index_version,
        )

    if provider_name in {"local", "bge_m3", "huggingface"}:
        from app.rag.embeddings.local_provider import (
            LocalSentenceTransformerEmbeddingProvider,
        )

        return LocalSentenceTransformerEmbeddingProvider(
            model_path=settings.local_embedding_model_path,
            model_name=settings.local_embedding_model_name,
            model_revision=settings.local_embedding_model_revision,
            dimension=settings.local_embedding_dimension,
            batch_size=settings.local_embedding_batch_size,
            device=settings.local_embedding_device,
            normalize_embeddings=settings.local_embedding_normalize_embeddings,
            index_version=settings.embedding_index_version,
        )

    raise RuntimeError(f"Unsupported embedding provider: {provider_name}")


def set_embedding_provider_for_testing(
    provider: EmbeddingProvider | None,
) -> None:
    global _testing_provider
    _testing_provider = provider
    get_embedding_provider.cache_clear()


def clear_embedding_provider_cache() -> None:
    get_embedding_provider.cache_clear()
