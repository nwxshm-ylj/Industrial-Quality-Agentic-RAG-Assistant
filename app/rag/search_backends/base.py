from __future__ import annotations

from typing import Protocol, runtime_checkable


class SearchBackendError(RuntimeError):
    """Base error that prevents SDK-specific exceptions leaking upward."""


class VectorSearchError(SearchBackendError):
    pass


class KeywordSearchError(SearchBackendError):
    pass


@runtime_checkable
class VectorSearchBackend(Protocol):
    def ensure_index(self) -> None: ...

    def upsert_document_chunks(
        self,
        doc_id: str,
        chunks: list[dict],
        *,
        index_status: str = "indexed",
        index_operation_id: str | None = None,
    ) -> None: ...

    def delete_by_doc_id(
        self,
        doc_id: str,
        *,
        index_operation_id: str | None = None,
        exclude_operation_id: str | None = None,
    ) -> None: ...

    def set_document_index_status(
        self,
        doc_id: str,
        status: str,
        *,
        index_operation_id: str,
    ) -> None: ...

    def count_indexed(self) -> int: ...

    def delete_all_except_operation(
        self,
        index_operation_id: str,
    ) -> None: ...

    def search(self, query: str, top_k: int = 5) -> list[dict]: ...


@runtime_checkable
class KeywordSearchBackend(Protocol):
    def ensure_index(self) -> None: ...

    def upsert_document_chunks(
        self,
        doc_id: str,
        chunks: list[dict],
        *,
        index_status: str = "indexed",
        index_operation_id: str | None = None,
    ) -> None: ...

    def delete_by_doc_id(
        self,
        doc_id: str,
        *,
        index_operation_id: str | None = None,
        exclude_operation_id: str | None = None,
    ) -> None: ...

    def set_document_index_status(
        self,
        doc_id: str,
        status: str,
        *,
        index_operation_id: str,
    ) -> None: ...

    def count_indexed(self) -> int: ...

    def delete_all_except_operation(
        self,
        index_operation_id: str,
    ) -> None: ...

    def search(self, query: str, top_k: int = 5) -> list[dict]: ...
