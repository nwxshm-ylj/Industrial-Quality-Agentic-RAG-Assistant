from __future__ import annotations

from functools import lru_cache

from app.multimodal.base import MultimodalEmbeddingProvider


_testing_provider: MultimodalEmbeddingProvider | None = None


@lru_cache(maxsize=1)
def get_multimodal_embedding_provider() -> MultimodalEmbeddingProvider:
    """Return one process-level provider; never recreate it per request."""

    if _testing_provider is not None:
        return _testing_provider

    from app.core.config import settings
    from app.multimodal.qwen_provider import QwenMultimodalEmbeddingProvider

    provider_name = settings.multimodal_embedding_provider.strip().lower()
    if provider_name != "qwen":
        raise RuntimeError(
            f"Unsupported multimodal embedding provider: {provider_name}"
        )
    return QwenMultimodalEmbeddingProvider(
        api_key=settings.qwen_multimodal_embedding_api_key,
        endpoint=settings.qwen_multimodal_embedding_base_url,
        model_name=settings.qwen_multimodal_embedding_model,
        dimension=settings.qwen_multimodal_embedding_dimension,
        index_version=settings.multimodal_embedding_index_version,
    )


def set_multimodal_embedding_provider_for_testing(
    provider: MultimodalEmbeddingProvider | None,
) -> None:
    global _testing_provider
    _testing_provider = provider
    get_multimodal_embedding_provider.cache_clear()


def clear_multimodal_embedding_provider_cache() -> None:
    get_multimodal_embedding_provider.cache_clear()
