from app.core.config import settings
from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.knowledge_graph.service import get_knowledge_graph_service
from app.rag.retriever import IndustrialRetriever
from app.traceability.service import ProblemTraceabilityService


retriever: IndustrialRetriever | None = None
traceability_service: ProblemTraceabilityService | None = None


def get_retriever() -> IndustrialRetriever:
    global retriever
    if retriever is None:
        retriever = IndustrialRetriever()
    return retriever


def get_traceability_service() -> ProblemTraceabilityService:
    global traceability_service
    if traceability_service is None:
        traceability_service = ProblemTraceabilityService(
            get_retriever(),
            graph_service=(
                get_knowledge_graph_service()
                if settings.knowledge_graph_enabled
                else None
            ),
            graph_enabled=settings.knowledge_graph_enabled,
            graph_result_limit=settings.knowledge_graph_result_limit,
        )
    return traceability_service


@observe_node("retrieve")
def retrieve_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    rewritten_query = state.get("rewritten_query") or question
    top_k = state.get("top_k", 5)
    query_features = state.get("query_features") or {}
    traceability_enabled = bool(query_features.get("traceability_required", False))
    retrieval_top_k = max(top_k * 4, 20) if traceability_enabled else top_k

    retrieval_result = get_retriever().retrieve_with_metadata(
        question=rewritten_query,
        top_k=retrieval_top_k,
        filters=state.get("retrieval_filters"),
        multimodal_query=state.get("multimodal_query"),
    )
    trace_result = None
    if traceability_enabled:
        trace_result = get_traceability_service().enrich_retrieval(
            rewritten_query,
            retrieval_result,
            top_k=top_k,
        )
        contexts = trace_result["contexts"]
        retrieval_metadata = trace_result["metadata"]
    else:
        contexts = retrieval_result["contexts"]
        retrieval_metadata = retrieval_result.get("metadata", {})

    citations = []

    for ctx in contexts:
        citations.append({
            "doc_id": ctx.get("doc_id"),
            "source": ctx.get("source"),
            "doc_type": ctx.get("doc_type"),
            "chunk_id": ctx.get("chunk_id"),
            "asset_id": ctx.get("asset_id"),
            "asset_path": ctx.get("asset_path"),
            "preview_url": ctx.get("preview_url"),
            "page_number": ctx.get("page_number"),
            "modality": ctx.get("modality"),
            "version": ctx.get("version"),
            "score": ctx.get("score"),
            "retrieval_source": ctx.get("retrieval_source"),
            "vector_score": ctx.get("vector_score"),
            "bm25_score": ctx.get("bm25_score"),
            "keyword_score": ctx.get("keyword_score"),
            "hybrid_score": ctx.get("hybrid_score"),
            "rrf_score": ctx.get("rrf_score"),
            "weighted_score": ctx.get("weighted_score"),
            "rerank_score": ctx.get("rerank_score"),
            "final_score_type": ctx.get("final_score_type"),
            "cross_modal_rrf_score": ctx.get("cross_modal_rrf_score"),
            "text_hybrid_score": ctx.get("text_hybrid_score"),
            "multimodal_score": ctx.get("multimodal_score"),
            "traceability_role": ctx.get("traceability_role"),
            "quality_entities": ctx.get("quality_entities"),
        })


    result = {
        "contexts": contexts,
        "citations": citations,
        "retrieval_metadata": retrieval_metadata,
    }
    if trace_result is not None:
        metadata = trace_result["metadata"]
        result.update(
            {
                "case_result": {
                    "question": question,
                    "retrieval_query": rewritten_query,
                    "entities": trace_result.get("entities", {}),
                    "evidence_count": len(
                        [
                            context
                            for context in contexts
                            if context.get("doc_type") != "KNOWLEDGE_GRAPH"
                        ]
                    ),
                    "evidence_by_type": metadata.get(
                        "traceability_document_type_counts",
                        {},
                    ),
                    "missing_evidence_types": metadata.get(
                        "traceability_missing_evidence_types",
                        [],
                    ),
                    "knowledge_graph": trace_result.get("knowledge_graph", {}),
                },
                "knowledge_graph_metadata": {
                    "knowledge_graph_enabled": metadata.get(
                        "knowledge_graph_enabled",
                        False,
                    ),
                    "knowledge_graph_degraded": metadata.get(
                        "knowledge_graph_degraded",
                        False,
                    ),
                    "knowledge_graph_degraded_reason": metadata.get(
                        "knowledge_graph_degraded_reason"
                    ),
                    "knowledge_graph_path_count": metadata.get(
                        "knowledge_graph_path_count",
                        0,
                    ),
                },
            }
        )
    return result
