from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.rag.retriever import IndustrialRetriever


retriever: IndustrialRetriever | None = None


def get_retriever() -> IndustrialRetriever:
    global retriever
    if retriever is None:
        retriever = IndustrialRetriever()
    return retriever


@observe_node("retrieve")
def retrieve_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    rewritten_query = state.get("rewritten_query") or question
    top_k = state.get("top_k", 5)

    retrieval_result = get_retriever().retrieve_with_metadata(
        question=rewritten_query,
        top_k=top_k,
        filters=state.get("retrieval_filters"),
        multimodal_query=state.get("multimodal_query"),
    )
    contexts = retrieval_result["contexts"]

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
        })


    return {
        "contexts": contexts,
        "citations": citations,
        "retrieval_metadata": retrieval_result.get("metadata", {}),
    }
