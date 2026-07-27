from __future__ import annotations

import re
from functools import lru_cache
from time import perf_counter

from app.core.logger import log_business_event
from app.knowledge_graph.base import KnowledgeGraphBackend
from app.knowledge_graph.neo4j_backend import get_neo4j_backend


class KnowledgeGraphService:
    def __init__(self, backend: KnowledgeGraphBackend) -> None:
        self.backend = backend

    def sync_quality_cases(self, cases: list[dict]) -> int:
        started_at = perf_counter()
        self.backend.ensure_schema()
        count = 0
        for case in cases:
            self.backend.upsert_quality_case(case)
            count += 1
        log_business_event(
            "knowledge_graph_cases_synced",
            status="success",
            case_count=count,
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return count

    def search_cases(self, question: str, limit: int = 5) -> dict:
        started_at = perf_counter()
        tokens = self._extract_tokens(question)
        paths = self.backend.search_paths(tokens, limit)
        context = self._format_paths(paths)
        log_business_event(
            "knowledge_graph_searched",
            status="success",
            path_count=len(paths),
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return {
            "tokens": tokens,
            "paths": paths,
            "path_count": len(paths),
            "context": context,
        }

    @staticmethod
    def _extract_tokens(question: str) -> list[str]:
        values = re.findall(r"[A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", question)
        stopwords = {"什么", "如何", "哪个", "可能", "原因", "案例", "历史", "查询"}
        tokens = []
        for value in values:
            normalized = value.lower()
            if normalized not in stopwords and normalized not in tokens:
                tokens.append(normalized)
        return tokens[:12]

    @staticmethod
    def _format_paths(paths: list[dict]) -> str:
        if not paths:
            return "知识图谱未找到相关路径。"
        lines = []
        for index, path in enumerate(paths, start=1):
            nodes = path.get("nodes", [])
            relationships = path.get("relationships", [])
            names = [str(node.get("name", "unknown")) for node in nodes]
            parts = []
            for offset, name in enumerate(names):
                parts.append(name)
                if offset < len(relationships):
                    parts.append(f"-[{relationships[offset]}]->")
            lines.append(f"图谱路径{index}: {' '.join(parts)}")
        return "\n".join(lines)


@lru_cache(maxsize=1)
def get_knowledge_graph_service() -> KnowledgeGraphService:
    return KnowledgeGraphService(get_neo4j_backend())
