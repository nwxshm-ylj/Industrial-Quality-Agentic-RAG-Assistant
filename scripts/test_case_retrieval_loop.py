from __future__ import annotations

import importlib

from app.graph.nodes.evidence_judge_node import (
    evidence_judge_node,
    route_after_evidence_judge,
)
from app.graph.nodes.intent_router_node import route_after_intent
from app.graph.workflow import industrial_rag_app


retrieve_node_module = importlib.import_module("app.graph.nodes.retrieve_node")


class _FakeRetriever:
    def __init__(self) -> None:
        self.received_query: str | None = None
        self.received_top_k: int | None = None

    def retrieve_with_metadata(
        self,
        question,
        top_k=5,
        filters=None,
        multimodal_query=None,
    ):
        self.received_query = question
        self.received_top_k = top_k
        return {
            "contexts": [
                {
                    "doc_id": "lesson-1",
                    "chunk_id": "lesson-1-c1",
                    "source": "LL-weld-deviation.pptx",
                    "doc_type": "LESSON_LEARNED",
                    "text": "A historical welding case identified trajectory deviation.",
                    "score": 0.82,
                    "evidence_signal_score": 0.82,
                    "retrieval_source": "vector+keyword",
                }
            ],
            "metadata": {"retrieval_mode": "hybrid"},
        }


class _FakeTraceabilityService:
    def enrich_retrieval(self, question, retrieval, *, top_k):
        contexts = list(retrieval["contexts"])
        contexts.append(
            {
                "chunk_id": "quality_traceability_paths",
                "source": "Neo4j.quality_traceability_graph",
                "doc_type": "KNOWLEDGE_GRAPH",
                "text": "weld_deviation -[MENTIONS]-> lesson-1-c1 -[HAS_CHUNK]-> LL",
                "score": 1.0,
                "evidence_signal_score": 1.0,
                "retrieval_source": "knowledge_graph",
                "traceability_role": "relationship_evidence",
            }
        )
        return {
            "entities": {
                "failure_modes": [
                    {"canonical_key": "weld_deviation", "name": "weld deviation"}
                ]
            },
            "contexts": contexts,
            "metadata": {
                **retrieval["metadata"],
                "traceability_enabled": True,
                "traceability_document_type_counts": {"LESSON_LEARNED": 1},
                "traceability_missing_evidence_types": [
                    "STANDARD_WORK_DOCUMENT",
                    "PFMEA",
                    "AFTERSALES_DOCUMENT",
                ],
                "knowledge_graph_enabled": True,
                "knowledge_graph_degraded": False,
                "knowledge_graph_path_count": 1,
            },
            "knowledge_graph": {"paths": [{}], "path_count": 1},
        }


def main() -> None:
    graph = industrial_rag_app.get_graph()
    assert "case_retriever" not in graph.nodes
    assert any(
        edge.source == "query_rewriter" and edge.target == "retrieve"
        for edge in graph.edges
    )
    assert route_after_intent({"intent": "rag"}) == "rag"

    state = {
        "question": "Are there similar welding deviation cases?",
        "rewritten_query": "weld deviation LessonLearn root cause corrective action",
        "intent": "rag",
        "query_features": {"traceability_required": True},
        "top_k": 5,
        "retry_count": 0,
        "retrieval_filters": None,
        "multimodal_query": None,
    }
    fake_retriever = _FakeRetriever()
    fake_traceability = _FakeTraceabilityService()
    original_retriever_factory = retrieve_node_module.get_retriever
    original_traceability_factory = retrieve_node_module.get_traceability_service
    retrieve_node_module.get_retriever = lambda: fake_retriever
    retrieve_node_module.get_traceability_service = lambda: fake_traceability
    try:
        result = retrieve_node_module.retrieve_node.__wrapped__(state)
    finally:
        retrieve_node_module.get_retriever = original_retriever_factory
        retrieve_node_module.get_traceability_service = original_traceability_factory

    assert fake_retriever.received_query == state["rewritten_query"]
    assert fake_retriever.received_top_k == 20
    assert result["case_result"]["question"] == state["question"]
    assert result["knowledge_graph_metadata"]["knowledge_graph_path_count"] == 1
    assert any(
        item["retrieval_source"] == "knowledge_graph"
        for item in result["citations"]
    )

    judge_result = evidence_judge_node.__wrapped__({**state, **result})
    assert judge_result["evidence_enough"] is True
    assert route_after_evidence_judge({**state, **judge_result}) == "generate"
    print("Unified retrieve node case traceability loop test passed")


if __name__ == "__main__":
    main()
