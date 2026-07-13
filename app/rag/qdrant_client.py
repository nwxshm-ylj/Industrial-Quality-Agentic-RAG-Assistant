from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def get_qdrant_client() -> Any:
    """Return one Qdrant client per application process."""

    from qdrant_client import QdrantClient

    from app.core.config import settings

    return QdrantClient(url=settings.qdrant_url)


def clear_qdrant_client_cache() -> None:
    get_qdrant_client.cache_clear()
