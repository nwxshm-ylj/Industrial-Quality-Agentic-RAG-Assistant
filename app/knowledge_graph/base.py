from __future__ import annotations

from typing import Protocol


class KnowledgeGraphError(RuntimeError):
    pass


class KnowledgeGraphBackend(Protocol):
    def ensure_schema(self) -> None: ...

    def upsert_document_chunks(
        self,
        document: dict,
        chunks: list[dict],
    ) -> None: ...

    def delete_document(self, doc_id: str) -> None: ...

    def search_traceability(
        self,
        entity_keys: list[str],
        limit: int,
    ) -> list[dict]: ...

    def close(self) -> None: ...
