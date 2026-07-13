from __future__ import annotations

from typing import Any, Callable

from app.rag.opensearch_client import get_opensearch_client
from app.rag.search_backends.base import KeywordSearchError


class OpenSearchKeywordBackend:
    """OpenSearch keyword backend with SDK exceptions contained here."""

    def __init__(
        self,
        *,
        index_name: str,
        client: Any | None = None,
        bulk_executor: Callable[..., Any] | None = None,
    ) -> None:
        if not index_name:
            raise ValueError("OpenSearch index name is required")
        self.index_name = index_name
        self.client = client or get_opensearch_client()
        self._bulk_executor = bulk_executor

    @property
    def bulk_executor(self) -> Callable[..., Any]:
        if self._bulk_executor is None:
            from opensearchpy.helpers import bulk

            self._bulk_executor = bulk
        return self._bulk_executor

    def ensure_index(self) -> None:
        try:
            if self.client.indices.exists(index=self.index_name):
                return
            self.client.indices.create(
                index=self.index_name,
                body=self.index_definition(),
            )
        except Exception as exc:
            raise KeywordSearchError(
                f"Unable to ensure OpenSearch index {self.index_name}: {exc}"
            ) from exc

    def upsert_document_chunks(
        self,
        doc_id: str,
        chunks: list[dict],
        *,
        index_status: str = "indexed",
        index_operation_id: str | None = None,
    ) -> None:
        if not chunks:
            return

        try:
            self.ensure_index()
            actions = []
            for index, chunk in enumerate(chunks):
                metadata = chunk.get("metadata", {})
                chunk_id = metadata.get("chunk_id") or f"{doc_id}_{index}"
                actions.append(
                    {
                        "_op_type": "index",
                        "_index": self.index_name,
                        "_id": chunk_id,
                        "_source": {
                            "doc_id": doc_id,
                            "chunk_id": chunk_id,
                            "chunk_index": metadata.get("chunk_index", index),
                            "text": chunk["text"],
                            "source": metadata.get("source"),
                            "doc_type": metadata.get("doc_type"),
                            "version": metadata.get("version"),
                            "index_status": index_status,
                            "index_operation_id": index_operation_id,
                        },
                    }
                )
            self.bulk_executor(
                self.client,
                actions,
                refresh="wait_for",
                raise_on_error=True,
            )
        except KeywordSearchError:
            raise
        except Exception as exc:
            raise KeywordSearchError(
                f"Unable to index document {doc_id} in OpenSearch: {exc}"
            ) from exc

    def delete_by_doc_id(
        self,
        doc_id: str,
        *,
        index_operation_id: str | None = None,
        exclude_operation_id: str | None = None,
    ) -> None:
        try:
            if not self.client.indices.exists(index=self.index_name):
                return
            filters = [{"term": {"doc_id": doc_id}}]
            if index_operation_id:
                filters.append(
                    {"term": {"index_operation_id": index_operation_id}}
                )
            must_not = []
            if exclude_operation_id:
                must_not.append(
                    {"term": {"index_operation_id": exclude_operation_id}}
                )
            self.client.delete_by_query(
                index=self.index_name,
                body={
                    "query": {
                        "bool": {
                            "filter": filters,
                            "must_not": must_not,
                        }
                    }
                },
                conflicts="proceed",
                refresh=True,
            )
        except Exception as exc:
            raise KeywordSearchError(
                f"Unable to delete OpenSearch data for document {doc_id}: {exc}"
            ) from exc

    def set_document_index_status(
        self,
        doc_id: str,
        status: str,
        *,
        index_operation_id: str,
    ) -> None:
        try:
            self.client.update_by_query(
                index=self.index_name,
                body={
                    "script": {
                        "source": "ctx._source.index_status = params.status",
                        "lang": "painless",
                        "params": {"status": status},
                    },
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"doc_id": doc_id}},
                                {
                                    "term": {
                                        "index_operation_id": index_operation_id
                                    }
                                },
                            ]
                        }
                    },
                },
                conflicts="proceed",
                refresh=True,
            )
        except Exception as exc:
            raise KeywordSearchError(
                f"Unable to update OpenSearch status for document {doc_id}: {exc}"
            ) from exc

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "size": top_k,
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": [
                                            "text^3",
                                            "text.exact^2",
                                            "source",
                                            "doc_type",
                                        ],
                                        "type": "best_fields",
                                    }
                                }
                            ],
                            "filter": [
                                {"term": {"index_status": "indexed"}}
                            ],
                        }
                    },
                },
            )
            return [self._to_result(hit) for hit in response["hits"]["hits"]]
        except Exception as exc:
            raise KeywordSearchError(f"OpenSearch search failed: {exc}") from exc

    def count_indexed(self) -> int:
        try:
            if not self.client.indices.exists(index=self.index_name):
                return 0
            result = self.client.count(
                index=self.index_name,
                body={
                    "query": {
                        "term": {
                            "index_status": "indexed",
                        }
                    }
                },
            )
            return int(result["count"])
        except Exception as exc:
            raise KeywordSearchError(
                f"Unable to count indexed OpenSearch documents: {exc}"
            ) from exc

    def delete_all_except_operation(
        self,
        index_operation_id: str,
    ) -> None:
        try:
            if not self.client.indices.exists(index=self.index_name):
                return
            self.client.delete_by_query(
                index=self.index_name,
                body={
                    "query": {
                        "bool": {
                            "must_not": [
                                {
                                    "term": {
                                        "index_operation_id": index_operation_id
                                    }
                                }
                            ]
                        }
                    }
                },
                conflicts="proceed",
                refresh=True,
            )
        except Exception as exc:
            raise KeywordSearchError(
                f"Unable to clean stale OpenSearch migration data: {exc}"
            ) from exc

    def is_available(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    @staticmethod
    def index_definition() -> dict:
        return {
            "settings": {
                "index": {
                    "max_ngram_diff": 2,
                },
                "analysis": {
                    "tokenizer": {
                        "industrial_ngram_tokenizer": {
                            "type": "ngram",
                            "min_gram": 1,
                            "max_gram": 3,
                            "token_chars": ["letter", "digit"],
                        }
                    },
                    "analyzer": {
                        "industrial_ngram": {
                            "type": "custom",
                            "tokenizer": "industrial_ngram_tokenizer",
                            "filter": ["lowercase"],
                        }
                    },
                }
            },
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "text": {
                        "type": "text",
                        "analyzer": "industrial_ngram",
                        "search_analyzer": "standard",
                        "fields": {
                            "exact": {
                                "type": "keyword",
                                "ignore_above": 256,
                            }
                        },
                    },
                    "source": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "doc_type": {"type": "keyword"},
                    "version": {"type": "keyword"},
                    "index_status": {"type": "keyword"},
                    "index_operation_id": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                },
            },
        }

    @staticmethod
    def _to_result(hit: dict) -> dict:
        source = hit.get("_source", {})
        return {
            "text": source.get("text", ""),
            "source": source.get("source", ""),
            "doc_type": source.get("doc_type", ""),
            "doc_id": source.get("doc_id", ""),
            "chunk_id": source.get("chunk_id", ""),
            "version": source.get("version", ""),
            "score": float(hit.get("_score") or 0.0),
            "retrieval_source": "keyword",
        }
