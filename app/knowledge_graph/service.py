from __future__ import annotations

from functools import lru_cache
from time import perf_counter

from app.core.logger import log_business_event
from app.knowledge_graph.base import KnowledgeGraphBackend
from app.knowledge_graph.neo4j_backend import get_neo4j_backend
from app.traceability.entity_linker import QualityEntityLinker


class KnowledgeGraphService:
    def __init__(self, backend: KnowledgeGraphBackend) -> None:
        self.backend = backend

    def sync_document(self, document: dict, chunks: list[dict]) -> int:
        started_at = perf_counter()
        self.backend.ensure_schema()
        self.backend.upsert_document_chunks(document, chunks)
        log_business_event(
            "knowledge_graph_document_synced",
            status="success",
            doc_id=document.get("doc_id"),
            doc_type=document.get("doc_type"),
            chunk_count=len(chunks),
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        started_at = perf_counter()
        self.backend.delete_document(doc_id)
        log_business_event(
            "knowledge_graph_document_deleted",
            status="success",
            doc_id=doc_id,
            latency_ms=(perf_counter() - started_at) * 1000,
        )

    def search_traceability(
        self,
        question: str,
        *,
        entities: dict | None = None,
        limit: int = 5,
    ) -> dict:
        started_at = perf_counter()
        linked_entities = entities or QualityEntityLinker().link(question)
        entity_keys = [
            item["canonical_key"]
            for values in linked_entities.values()
            for item in values
        ]
        paths = (
            self.backend.search_traceability(entity_keys, limit)
            if entity_keys
            else []
        )
        result = self._build_search_result(entity_keys, paths)
        log_business_event(
            "knowledge_graph_traceability_searched",
            status="success",
            path_count=len(paths),
            entity_count=len(entity_keys),
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return result

    @staticmethod
    def _build_search_result(tokens: list[str], paths: list[dict]) -> dict:
        return {
            "tokens": tokens,
            "paths": paths,
            "path_count": len(paths),
            "context": KnowledgeGraphService._format_paths(paths),
        }

    @staticmethod
    def _format_paths(paths: list[dict]) -> str:
        if not paths:
            return "知识图谱未找到相关证据路径。"
        lines = []
        for index, path in enumerate(paths, start=1):
            nodes = [node for node in path.get("nodes", []) if node.get("name")]
            relationships = path.get("relationships", [])
            parts = []
            for offset, node in enumerate(nodes):
                parts.append(str(node.get("name", "unknown")))
                if offset < len(relationships):
                    parts.append(f"-[{relationships[offset]}]->")
            lines.append(f"证据路径{index}: {' '.join(parts)}")
        return "\n".join(lines)


@lru_cache(maxsize=1)
def get_knowledge_graph_service() -> KnowledgeGraphService:
    return KnowledgeGraphService(get_neo4j_backend())
