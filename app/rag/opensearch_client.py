from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.parse import urlparse


@lru_cache(maxsize=1)
def get_opensearch_client() -> Any:
    """Return one configured OpenSearch connection pool per process."""

    from opensearchpy import OpenSearch
    from urllib3.util import Timeout

    from app.core.config import settings

    parsed = urlparse(settings.opensearch_url)
    if not parsed.hostname:
        raise ValueError("OPENSEARCH_URL must include a hostname")

    options: dict[str, Any] = {
        "hosts": [
            {
                "host": parsed.hostname,
                "port": parsed.port or (443 if parsed.scheme == "https" else 9200),
                "timeout": Timeout(
                    connect=settings.opensearch_connect_timeout,
                    read=settings.opensearch_read_timeout,
                ),
            }
        ],
        "use_ssl": parsed.scheme == "https",
        "verify_certs": settings.opensearch_verify_certs,
        "pool_maxsize": settings.opensearch_pool_maxsize,
        "max_retries": settings.opensearch_max_retries,
        "retry_on_timeout": settings.opensearch_retry_on_timeout,
    }
    if settings.opensearch_username and settings.opensearch_password:
        options["http_auth"] = (
            settings.opensearch_username,
            settings.opensearch_password,
        )

    return OpenSearch(**options)


def clear_opensearch_client_cache() -> None:
    get_opensearch_client.cache_clear()
