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

    _CASE_BUNDLE_MAX_CHUNKS = 3

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
        task_mode: str = "cause_trace",
    ) -> dict:
        """Add traceability semantics to an existing hybrid-search result.

        The caller owns retrieval. This keeps document QA and case-style
        questions on one Qdrant/OpenSearch pipeline and prevents a second
        search when relationship evidence is requested.
        """
        started_at = perf_counter()
        candidates = retrieval.get("contexts", [])
        if task_mode == "case_search":
            contexts = self._select_case_evidence(candidates, top_k=top_k)
        else:
            contexts = self._select_diverse_evidence(candidates, top_k=top_k)

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
                "task_mode": task_mode,
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
                "traceability_evidence_bundle_count": sum(
                    1 for context in contexts if context.get("evidence_bundle")
                ),
                "traceability_bundled_chunk_count": sum(
                    int(context.get("evidence_chunk_count") or 1)
                    for context in contexts
                    if context.get("doc_type") != "KNOWLEDGE_GRAPH"
                ),
            }
        )
        cases = self._group_cases(contexts)
        metadata["traceability_case_count"] = len(cases)
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
            "cases": cases,
            "metadata": metadata,
            "knowledge_graph": graph_result,
        }

    @staticmethod
    def _case_key(item: dict[str, Any]) -> str:
        return str(
            item.get("case_id")
            or item.get("doc_id")
            or item.get("source")
            or item.get("chunk_id")
        )

    @staticmethod
    def _chunk_index(item: dict[str, Any]) -> int | None:
        value = item.get("chunk_index")
        return value if isinstance(value, int) else None

    @classmethod
    def _bundle_relation_score(
        cls,
        anchor: dict[str, Any],
        candidate: dict[str, Any],
    ) -> int:
        """Score transparent structural links without semantic inference."""
        anchor_chunk_id = str(anchor.get("chunk_id") or "")
        candidate_chunk_id = str(candidate.get("chunk_id") or "")
        if (
            candidate.get("adjacent_to_chunk_id") == anchor_chunk_id
            or anchor.get("adjacent_to_chunk_id") == candidate_chunk_id
        ):
            return 4

        anchor_index = cls._chunk_index(anchor)
        candidate_index = cls._chunk_index(candidate)
        if anchor_index is None or candidate_index is None:
            return 0

        same_page = (
            anchor.get("page_number") is not None
            and anchor.get("page_number") == candidate.get("page_number")
        )
        same_table = (
            anchor.get("table_index") is not None
            and anchor.get("table_index") == candidate.get("table_index")
        )
        if same_page and same_table:
            return 3
        if same_page and abs(candidate_index - anchor_index) == 1:
            return 2
        return 0

    @classmethod
    def _build_case_evidence_bundle(
        cls,
        case_key: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Combine structurally linked chunks while preserving the anchor fields."""
        anchor = items[0]
        seen_chunk_ids: set[str] = set()
        unique_items: list[dict[str, Any]] = []
        for item in items:
            chunk_id = str(item.get("chunk_id") or "")
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            unique_items.append(item)

        related = [
            item
            for item in unique_items[1:]
            if cls._bundle_relation_score(anchor, item) > 0
        ]
        related.sort(
            key=lambda item: (
                -cls._bundle_relation_score(anchor, item),
                abs(
                    (cls._chunk_index(item) or 0)
                    - (cls._chunk_index(anchor) or 0)
                ),
                -float(item.get("score") or 0.0),
            )
        )
        members = [anchor, *related[: cls._CASE_BUNDLE_MAX_CHUNKS - 1]]
        members.sort(
            key=lambda item: (
                cls._chunk_index(item) is None,
                cls._chunk_index(item) or 0,
            )
        )

        chunk_ids = [
            str(item.get("chunk_id")) for item in members if item.get("chunk_id")
        ]
        bundle = dict(anchor)
        bundle.update(
            {
                "text": "\n\n".join(
                    str(item.get("text") or "").strip()
                    for item in members
                    if str(item.get("text") or "").strip()
                ),
                "evidence_bundle_id": f"case:{case_key}",
                "evidence_chunk_ids": chunk_ids,
                "evidence_chunk_count": len(chunk_ids),
                "evidence_bundle": len(chunk_ids) > 1,
            }
        )
        return bundle

    @classmethod
    def _select_case_evidence(cls, candidates: list[dict], *, top_k: int) -> list[dict]:
        if top_k <= 0:
            return []
        prepared: list[dict] = []
        for candidate in candidates:
            item = dict(candidate)
            doc_type = normalize_document_type(item.get("doc_type"))
            item["doc_type"] = doc_type
            item["traceability_role"] = traceability_role(doc_type)
            prepared.append(item)

        prepared.sort(
            key=lambda item: (
                item.get("doc_type")
                in {"LESSON_LEARNED", "AFTERSALES_DOCUMENT"}
                or bool(item.get("case_id")),
                float(item.get("score") or 0.0),
            ),
            reverse=True,
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in prepared:
            grouped[cls._case_key(item)].append(item)

        selected: list[dict[str, Any]] = []
        for case_key, items in grouped.items():
            selected.append(cls._build_case_evidence_bundle(case_key, items))
            if len(selected) >= top_k:
                break
        return selected

    @staticmethod
    def _group_cases(contexts: list[dict]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for context in contexts:
            if context.get("doc_type") == "KNOWLEDGE_GRAPH":
                continue
            if (
                context.get("doc_type")
                not in {"LESSON_LEARNED", "AFTERSALES_DOCUMENT"}
                and not context.get("case_id")
            ):
                continue
            case_id = str(
                context.get("case_id")
                or context.get("doc_id")
                or context.get("source")
                or context.get("chunk_id")
                or "unknown"
            )
            group = grouped.setdefault(
                case_id,
                {
                    "case_id": case_id,
                    "doc_id": context.get("doc_id"),
                    "source": context.get("source"),
                    "doc_type": context.get("doc_type"),
                    "evidence_count": 0,
                    "evidence_chunk_count": 0,
                    "chunk_ids": [],
                    "traceability_roles": [],
                },
            )
            group["evidence_count"] += 1
            evidence_chunk_ids = context.get("evidence_chunk_ids") or [
                context.get("chunk_id")
            ]
            group["evidence_chunk_count"] += sum(
                1 for chunk_id in evidence_chunk_ids if chunk_id
            )
            for chunk_id in evidence_chunk_ids:
                if chunk_id and chunk_id not in group["chunk_ids"]:
                    group["chunk_ids"].append(chunk_id)
            role = context.get("traceability_role")
            if role and role not in group["traceability_roles"]:
                group["traceability_roles"].append(role)
        return list(grouped.values())

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
