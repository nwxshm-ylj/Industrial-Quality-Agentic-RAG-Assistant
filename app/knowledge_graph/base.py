from __future__ import annotations

from typing import Protocol


class KnowledgeGraphError(RuntimeError):
    pass


class KnowledgeGraphBackend(Protocol):
    def ensure_schema(self) -> None: ...

    def upsert_quality_case(self, case: dict) -> None: ...

    def search_paths(self, tokens: list[str], limit: int) -> list[dict]: ...

    def close(self) -> None: ...
