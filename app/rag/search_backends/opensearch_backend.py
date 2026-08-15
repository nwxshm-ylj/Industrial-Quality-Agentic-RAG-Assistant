from __future__ import annotations

from typing import Any, Callable

from app.rag.opensearch_client import get_opensearch_client
from app.rag.retrieval_filters import RetrievalFilter
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
        self._index_ready = False

    @property
    def bulk_executor(self) -> Callable[..., Any]:
        if self._bulk_executor is None:
            from opensearchpy.helpers import bulk

            self._bulk_executor = bulk
        return self._bulk_executor

    def ensure_index(self) -> None:
        if self._index_ready:
            return
        try:
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.put_mapping(
                    index=self.index_name,
                    body={"properties": self.chunk_metadata_properties()},
                )
                self._index_ready = True
                return
            self.client.indices.create(
                index=self.index_name,
                body=self.index_definition(),
            )
            self._index_ready = True
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
                            **_chunk_metadata_source(metadata),
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

    def search(
        self,
        query: str,
        top_k: int = 5,
        *,
        filters: RetrievalFilter | None = None,
    ) -> list[dict]:
        try:
            search_filters: list[dict[str, Any]] = [
                {"term": {"index_status": "indexed"}}
            ]
            if filters is not None:
                for key, values in (
                    ("doc_id", filters.doc_ids),
                    ("doc_type", filters.doc_types),
                    ("version", filters.versions),
                    ("source.keyword", filters.sources),
                ):
                    if values:
                        search_filters.append({"terms": {key: list(values)}})
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
                                            "heading_path^2.5",
                                            "quality_entity_terms^4",
                                            "source",
                                            "doc_type",
                                        ],
                                        "type": "best_fields",
                                    }
                                }
                            ],
                            "filter": search_filters,
                        }
                    },
                },
            )
            return [self._to_result(hit) for hit in response["hits"]["hits"]]
        except Exception as exc:
            raise KeywordSearchError(f"OpenSearch search failed: {exc}") from exc

    def get_adjacent_chunks(
        self,
        seeds: list[dict[str, Any]],
        *,
        window: int = 1,
    ) -> list[dict]:
        """Fetch neighboring chunks for ranked seeds with one OpenSearch call."""
        if window <= 0:
            return []
        valid_seeds = [
            seed
            for seed in seeds
            if seed.get("doc_id") and isinstance(seed.get("chunk_index"), int)
        ]
        if not valid_seeds:
            return []

        seed_ids = [
            str(seed.get("chunk_id"))
            for seed in valid_seeds
            if seed.get("chunk_id")
        ]
        should = []
        for seed in valid_seeds:
            chunk_index = int(seed["chunk_index"])
            should.append(
                {
                    "bool": {
                        "filter": [
                            {"term": {"doc_id": str(seed["doc_id"])}},
                            {
                                "range": {
                                    "chunk_index": {
                                        "gte": max(0, chunk_index - window),
                                        "lte": chunk_index + window,
                                    }
                                }
                            },
                        ]
                    }
                }
            )
        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "size": len(valid_seeds) * window * 2,
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"index_status": "indexed"}}
                            ],
                            "should": should,
                            "minimum_should_match": 1,
                            "must_not": (
                                [{"terms": {"chunk_id": seed_ids}}]
                                if seed_ids
                                else []
                            ),
                        }
                    },
                },
            )
            return [self._to_result(hit) for hit in response["hits"]["hits"]]
        except Exception as exc:
            raise KeywordSearchError(
                f"OpenSearch adjacent chunk lookup failed: {exc}"
            ) from exc

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
                    **OpenSearchKeywordBackend.chunk_metadata_properties(),
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
            "chunk_index": source.get("chunk_index"),
            "version": source.get("version", ""),
            "section_type": source.get("section_type"),
            "heading_path": source.get("heading_path"),
            "page_number": source.get("page_number"),
            "page_start": source.get("page_start"),
            "page_end": source.get("page_end"),
            "table_index": source.get("table_index"),
            "asset_ids": source.get("asset_ids", []),
            "parser_version": source.get("parser_version"),
            "chunk_strategy": source.get("chunk_strategy"),
            "quality_entities": source.get("quality_entities", {}),
            "quality_entity_terms": source.get("quality_entity_terms", []),
            "vehicle_models": source.get("vehicle_models", []),
            "systems": source.get("systems", []),
            "components": source.get("components", []),
            "processes": source.get("processes", []),
            "stations": source.get("stations", []),
            "failure_modes": source.get("failure_modes", []),
            "symptoms": source.get("symptoms", []),
            "root_causes": source.get("root_causes", []),
            "process_parameters": source.get("process_parameters", []),
            "control_measures": source.get("control_measures", []),
            "corrective_actions": source.get("corrective_actions", []),
            "score": float(hit.get("_score") or 0.0),
            "retrieval_source": "keyword",
        }

    @staticmethod
    def chunk_metadata_properties() -> dict:
        return {
            "file_ext": {"type": "keyword"},
            "parser": {"type": "keyword"},
            "parser_name": {"type": "keyword"},
            "parser_version": {"type": "keyword"},
            "chunk_strategy": {"type": "keyword"},
            "token_counter": {"type": "keyword"},
            "token_count": {"type": "integer"},
            "content_hash": {"type": "keyword"},
            "section_type": {"type": "keyword"},
            "heading_path": {
                "type": "text",
                "analyzer": "industrial_ngram",
                "search_analyzer": "standard",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
            },
            "page_number": {"type": "integer"},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
            "table_index": {"type": "integer"},
            "element_ids": {"type": "keyword"},
            "asset_ids": {"type": "keyword"},
            "bboxes": {"type": "object", "enabled": False},
            "quality_entities": {"type": "object", "enabled": False},
            "quality_entity_terms": {
                "type": "text",
                "analyzer": "industrial_ngram",
                "search_analyzer": "standard",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "vehicle_models": {"type": "keyword"},
            "systems": {"type": "keyword"},
            "components": {"type": "keyword"},
            "processes": {"type": "keyword"},
            "stations": {"type": "keyword"},
            "failure_modes": {"type": "keyword"},
            "symptoms": {"type": "keyword"},
            "root_causes": {"type": "keyword"},
            "process_parameters": {"type": "keyword"},
            "control_measures": {"type": "keyword"},
            "corrective_actions": {"type": "keyword"},
        }


_CHUNK_METADATA_FIELDS = tuple(
    OpenSearchKeywordBackend.chunk_metadata_properties().keys()
)


def _chunk_metadata_source(metadata: dict) -> dict:
    return {
        field: metadata[field]
        for field in _CHUNK_METADATA_FIELDS
        if field in metadata and metadata[field] is not None
    }
