from __future__ import annotations

import math
import re
from typing import Protocol, runtime_checkable


_TOKEN_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]",
    re.UNICODE,
)
_BREAK_CHARACTERS = frozenset("\n。！？；.!?;，,、:： \t")


@runtime_checkable
class TokenCounter(Protocol):
    """Offline token-budget interface used by chunkers and tests."""

    name: str

    def count(self, text: str) -> int:
        ...

    def split(self, text: str, max_tokens: int) -> list[str]:
        ...

    def tail(self, text: str, max_tokens: int) -> str:
        ...


class UnicodeTokenCounter:
    """Conservative offline estimator for mixed Chinese and Latin documents.

    This deliberately avoids downloading a model tokenizer or calling a paid API.
    A model-specific counter can later implement the same ``TokenCounter`` protocol.
    """

    name = "unicode-estimator-v1"

    def count(self, text: str) -> int:
        total = 0
        for token in _TOKEN_PATTERN.findall(text or ""):
            if token.isascii() and (token.isalnum() or "_" in token):
                total += max(1, math.ceil(len(token) / 4))
            else:
                total += 1
        return total

    def split(self, text: str, max_tokens: int) -> list[str]:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        remaining = (text or "").strip()
        if not remaining:
            return []

        parts: list[str] = []
        while self.count(remaining) > max_tokens:
            end = self._largest_prefix(remaining, max_tokens)
            end = self._preferred_break(remaining, end)
            if end <= 0:
                end = 1
            part = remaining[:end].strip()
            if part:
                parts.append(part)
            remaining = remaining[end:].strip()
        if remaining:
            parts.append(remaining)
        return parts

    def tail(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0 or not text:
            return ""
        if self.count(text) <= max_tokens:
            return text.strip()

        low = 0
        high = len(text)
        while low < high:
            middle = (low + high) // 2
            if self.count(text[middle:]) <= max_tokens:
                high = middle
            else:
                low = middle + 1
        start = low
        search_end = min(len(text), start + max(24, len(text) // 10))
        for index in range(start, search_end):
            if text[index] in _BREAK_CHARACTERS:
                start = index + 1
                break
        return text[start:].strip()

    def _largest_prefix(self, text: str, max_tokens: int) -> int:
        low = 1
        high = len(text)
        best = 1
        while low <= high:
            middle = (low + high) // 2
            if self.count(text[:middle]) <= max_tokens:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        return best

    @staticmethod
    def _preferred_break(text: str, end: int) -> int:
        lower_bound = max(0, int(end * 0.6))
        for index in range(end - 1, lower_bound - 1, -1):
            if text[index] in _BREAK_CHARACTERS:
                return index + 1
        return end
