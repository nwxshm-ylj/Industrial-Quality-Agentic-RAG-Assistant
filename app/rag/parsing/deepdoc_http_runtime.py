from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from time import perf_counter
from typing import Any, Mapping, Protocol
from urllib.parse import urljoin

import requests

from app.core.logger import log_business_event
from app.rag.parsing.exceptions import (
    DocumentParsingError,
    ParserUnavailableError,
)


class DeepDocHttpRuntime:
    """Reusable HTTP client for the isolated DeepDOC parser service."""

    def __init__(
        self,
        base_url: str,
        *,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 300.0,
        client: "_HttpClient | None" = None,
    ) -> None:
        normalized_url = (base_url or "").strip()
        if not normalized_url:
            raise ValueError("DEEPDOC_RUNTIME_URL is required")
        if connect_timeout_seconds <= 0 or read_timeout_seconds <= 0:
            raise ValueError("DeepDOC HTTP timeouts must be greater than zero")
        self.base_url = normalized_url.rstrip("/") + "/"
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self._client = client or requests.Session()

    def parse_pdf(self, path: Path, *, zoomin: int, max_pages: int) -> Any:
        started_at = perf_counter()
        endpoint = urljoin(self.base_url, "v1/parse")
        try:
            with path.open("rb") as file_handle:
                response = self._client.post(
                    endpoint,
                    files={"file": (path.name, file_handle, "application/pdf")},
                    data={"zoomin": str(zoomin), "max_pages": str(max_pages)},
                    timeout=(
                        self.connect_timeout_seconds,
                        self.read_timeout_seconds,
                    ),
                )
            if response.status_code >= 500:
                raise ParserUnavailableError(
                    f"DeepDOC Runtime HTTP {response.status_code}: "
                    f"{_response_detail(response)}"
                )
            if response.status_code >= 400:
                raise DocumentParsingError(
                    f"DeepDOC Runtime rejected PDF ({response.status_code}): "
                    f"{_response_detail(response)}"
                )
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise DocumentParsingError(
                    "DeepDOC Runtime returned a non-object JSON response"
                )
            log_business_event(
                "deepdoc_http_parse_completed",
                status="success",
                latency_ms=(perf_counter() - started_at) * 1000,
                filename=path.name,
                runtime_url=self.base_url,
            )
            return dict(payload)
        except (DocumentParsingError, ParserUnavailableError):
            raise
        except (requests.Timeout, requests.ConnectionError) as exc:
            _log_http_failure(path, self.base_url, started_at, exc)
            raise ParserUnavailableError(
                f"DeepDOC Runtime is unavailable: {exc}"
            ) from exc
        except (requests.RequestException, ValueError, TypeError) as exc:
            _log_http_failure(path, self.base_url, started_at, exc)
            raise DocumentParsingError(
                f"DeepDOC Runtime request failed: {exc}"
            ) from exc

    def readiness(self, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
        if timeout_seconds <= 0:
            raise ValueError("DeepDOC readiness timeout must be positive")
        endpoint = urljoin(self.base_url, "health/ready")
        try:
            response = self._client.get(
                endpoint,
                timeout=(timeout_seconds, timeout_seconds),
            )
            if response.status_code >= 400:
                raise ParserUnavailableError(
                    f"DeepDOC readiness HTTP {response.status_code}: "
                    f"{_response_detail(response)}"
                )
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise ParserUnavailableError(
                    "DeepDOC readiness returned invalid JSON"
                )
            return dict(payload)
        except ParserUnavailableError:
            raise
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise ParserUnavailableError(
                f"DeepDOC readiness failed: {exc}"
            ) from exc


@lru_cache(maxsize=4)
def get_deepdoc_http_runtime(
    base_url: str,
    connect_timeout_seconds: float = 5.0,
    read_timeout_seconds: float = 300.0,
) -> DeepDocHttpRuntime:
    return DeepDocHttpRuntime(
        base_url,
        connect_timeout_seconds=connect_timeout_seconds,
        read_timeout_seconds=read_timeout_seconds,
    )


class _HttpResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class _HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        files: Mapping[str, Any],
        data: Mapping[str, str],
        timeout: tuple[float, float],
    ) -> _HttpResponse: ...

    def get(
        self,
        url: str,
        *,
        timeout: tuple[float, float],
    ) -> _HttpResponse: ...


def _response_detail(response: _HttpResponse) -> str:
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return str(response.text or "")[:500]
    if isinstance(payload, Mapping):
        detail = payload.get("detail") or payload.get("error") or payload
        return str(detail)[:500]
    return str(payload)[:500]


def _log_http_failure(
    path: Path,
    runtime_url: str,
    started_at: float,
    error: Exception,
) -> None:
    log_business_event(
        "deepdoc_http_parse_failed",
        status="failed",
        latency_ms=(perf_counter() - started_at) * 1000,
        error_message=str(error),
        filename=path.name,
        runtime_url=runtime_url,
        error_type=type(error).__name__,
    )
