from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

import requests

from app.core.logger import log_business_event


class DocumentOcrError(RuntimeError):
    """Project-owned OCR exception that hides transport implementation details."""


class DocumentOcrProvider(Protocol):
    def extract_text(self, image_data_uri: str) -> str: ...


class DotsOcrHttpProvider:
    """Adapter for a privately deployed dots.OCR HTTP gateway.

    The project contract is JSON ``{"image": "data:image/..."}`` and a JSON
    response containing ``text`` (or ``output.text``). The gateway may adapt
    the native model-serving protocol without leaking it into services.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: float = 120.0,
        client: _HttpClient | None = None,
    ) -> None:
        if not endpoint:
            raise ValueError("DOTS_OCR_URL is required")
        if timeout_seconds <= 0:
            raise ValueError("OCR timeout must be greater than zero")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self._client = client or requests.Session()

    def extract_text(self, image_data_uri: str) -> str:
        if not image_data_uri.startswith("data:image/"):
            raise ValueError("OCR input must be a Base64 data:image URI")
        try:
            response = self._client.post(
                self.endpoint,
                json={"image": image_data_uri},
                timeout=(10.0, self.timeout_seconds),
            )
            response.raise_for_status()
            payload = response.json()
            text = payload.get("text") or (payload.get("output") or {}).get("text")
            if not isinstance(text, str):
                raise DocumentOcrError("dots.OCR response is missing text")
            return text.strip()
        except (DocumentOcrError, requests.RequestException, TypeError) as exc:
            log_business_event(
                "multimodal_ocr_failed",
                status="failed",
                error_message=str(exc),
                ocr_provider="dots_ocr",
            )
            if isinstance(exc, DocumentOcrError):
                raise
            raise DocumentOcrError(f"dots.OCR request failed: {exc}") from exc


class _HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, Any]: ...


class _HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        json: dict[str, str],
        timeout: tuple[float, float],
    ) -> _HttpResponse: ...


@lru_cache(maxsize=1)
def get_document_ocr_provider() -> DocumentOcrProvider | None:
    from app.core.config import settings

    if not settings.dots_ocr_url:
        return None
    return DotsOcrHttpProvider(
        endpoint=settings.dots_ocr_url,
        timeout_seconds=settings.dots_ocr_timeout_seconds,
    )
