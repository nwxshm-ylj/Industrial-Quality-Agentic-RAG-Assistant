from __future__ import annotations

import re
from typing import Any


SENSITIVE_KEYS = {
    "authorization",
    "password",
    "password_hash",
    "token",
    "access_token",
    "api_key",
    "secret",
    "jwt",
    "prompt",
    "question",
    "answer",
    "document_text",
    "content",
}

_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[a-z0-9._~+\-/]+=*")
_URL_CREDENTIAL_PATTERN = re.compile(
    r"(?i)([a-z][a-z0-9+.-]*://[^:/\s]+:)([^@/\s]+)(@)"
)
_QUERY_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|password|secret)=([^&\s]+)"
)


def sanitize_telemetry_value(value: Any, *, key: str | None = None) -> Any:
    normalized_key = (key or "").lower()
    if normalized_key in SENSITIVE_KEYS or any(
        fragment in normalized_key
        for fragment in ("password", "api_key", "secret", "authorization")
    ):
        return "[REDACTED]"

    if isinstance(value, dict):
        return {
            str(item_key): sanitize_telemetry_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_telemetry_value(item) for item in value]
    if isinstance(value, str):
        value = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        value = _URL_CREDENTIAL_PATTERN.sub(r"\1[REDACTED]\3", value)
        return _QUERY_SECRET_PATTERN.sub(r"\1=[REDACTED]", value)
    return value
