from __future__ import annotations

from collections import Counter, defaultdict
from time import perf_counter
from typing import TYPE_CHECKING, Any

from app.core.logger import log_business_event
from app.traceability.entity_linker import QualityEntityLinker
from app.traceability.taxonomy import normalize_document_type, traceability_role

if TYPE_CHECKING:
    from app.rag.retriever import IndustrialRetriever


class ProblemTraceabilityService:
    """Orchestrate one knowledge base into an evidence-oriented trace result."""

    def __init__(
        self,
        retriever: "IndustrialRetriever",
        *,
        entity_linker: QualityEntityLinker | None = None,
        graph_service: Any | None = None,
        graph_enabled: bool = False,
        graph_result_limit: int = 5,
    ) -> None:
        self.retriever = retriever
        self.entity_linker = entity_linker or QualityEntityLinker()
        self.graph_service = graph_service
        self.graph_enabled = graph_enabled
        self.graph_result_limit = graph_result_limit

    def trace(
        self,
        question: str,
        *,
        top_k: int = 5,
        filters: dict | None = None,
        multimodal_query: dict | None = None,
    ) -> dict:
        candidate_k = max(top_k * 4, 20)
        retrieval = self.retriever.retrieve_with_metadata(
            question=question,
            top_k=candidate_k,
            filters=filters,
            multimodal_query=multimodal_query,
        )
        return self.enrich_retrieval(question, retrieval, top_k=top_k)

    def enrich_retrieval(
        self,
        question: str,
        retrieval: dict,
        *,
        top_k: int = 5,
    ) -> dict:
        """Add traceability semantics to an existing hybrid-search result.

        The caller owns retrieval. This keeps document QA and case-style
        questions on one Qdrant/OpenSearch pipeline and prevents a second
        search when relationship evidence is requested.
        """
        started_at = perf_counter()
        contexts = self._select_diverse_evidence(
            retrieval.get("contexts", []),
            top_k=top_k,
        )

        entities = self.entity_linker.link(question)
        graph_result: dict[str, Any] = {
            "paths": [],
            "path_count": 0,
            "context": "",
        }
        graph_degraded = False
        graph_degraded_reason = None
        if self.graph_enabled and self.graph_service is not None:
            try:
                graph_result = self.graph_service.search_traceability(
                    question,
                    entities=entities,
                    limit=max(top_k, self.graph_result_limit),
                )
                if graph_result.get("path_count"):
                    contexts.append(
                        {
                            "text": graph_result["context"],
                            "source": "Neo4j.quality_traceability_graph",
                            "doc_type": "KNOWLEDGE_GRAPH",
                            "chunk_id": "quality_traceability_paths",
                            "score": 1.0,
                            "retrieval_source": "knowledge_graph",
                            "traceability_role": "relationship_evidence",
                            "quality_entities": entities,
                        }
                    )
            except Exception as exc:
                graph_degraded = True
                graph_degraded_reason = str(exc)
                log_business_event(
                    "traceability_graph_degraded",
                    status="degraded",
                    degraded=True,
                    degraded_reason=graph_degraded_reason,
                    error_message=graph_degraded_reason,
                )

        type_counts = Counter(
            context.get("doc_type", "GENERAL")
            for context in contexts
            if context.get("doc_type") != "KNOWLEDGE_GRAPH"
        )
        metadata = dict(retrieval.get("metadata", {}))
        metadata.update(
            {
                "traceability_enabled": True,
                "traceability_query_entities": entities,
                "traceability_document_type_counts": dict(type_counts),
                "traceability_missing_evidence_types": self._missing_evidence_types(
                    type_counts
                ),
                "knowledge_graph_enabled": self.graph_enabled,
                "knowledge_graph_degraded": graph_degraded,
                "knowledge_graph_degraded_reason": graph_degraded_reason,
                "knowledge_graph_path_count": graph_result.get("path_count", 0),
                "traceability_latency_ms": round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
            }
        )
        log_business_event(
            "problem_traceability_completed",
            status="success",
            context_count=len(contexts),
            graph_path_count=graph_result.get("path_count", 0),
            latency_ms=metadata["traceability_latency_ms"],
        )
        return {
            "question": question,
            "entities": entities,
            "contexts": contexts,
            "metadata": metadata,
            "knowledge_graph": graph_result,
        }

    @staticmethod
    def _select_diverse_evidence(candidates: list[dict], *, top_k: int) -> list[dict]:
        if top_k <= 0:
            return []
        grouped: dict[str, list[dict]] = defaultdict(list)
        for candidate in candidates:
            item = dict(candidate)
            doc_type = normalize_document_type(item.get("doc_type"))
            item["doc_type"] = doc_type
            item["traceability_role"] = traceability_role(doc_type)
            grouped[doc_type].append(item)

        selected: list[dict] = []
        # First pass preserves type diversity only among evidence that was
        # actually retrieved; it never manufactures or forces irrelevant types.
        for items in grouped.values():
            if items and len(selected) < top_k:
                selected.append(items.pop(0))

        remaining = sorted(
            (item for items in grouped.values() for item in items),
            key=lambda item: float(item.get("score") or 0.0),
            reverse=True,
        )
        selected.extend(remaining[: max(0, top_k - len(selected))])
        return selected

    @staticmethod
    def _missing_evidence_types(type_counts: Counter) -> list[str]:
        expected = (
            "STANDARD_WORK_DOCUMENT",
            "PFMEA",
            "AFTERSALES_DOCUMENT",
            "LESSON_LEARNED",
        )
        return [value for value in expected if not type_counts.get(value)]
