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
        top_k=top_k
    )
    contexts = retrieval_result["contexts"]

    citations = []

    for ctx in contexts:
        citations.append({
            "doc_id": ctx.get("doc_id"),
            "source": ctx.get("source"),
            "doc_type": ctx.get("doc_type"),
            "chunk_id": ctx.get("chunk_id"),
            "version": ctx.get("version"),
            "score": ctx.get("score"),
            "retrieval_source": ctx.get("retrieval_source"),
            "vector_score": ctx.get("vector_score"),
            "bm25_score": ctx.get("bm25_score"),
            "keyword_score": ctx.get("keyword_score"),
            "hybrid_score": ctx.get("hybrid_score"),
            "rrf_score": ctx.get("rrf_score"),
            "rerank_score": ctx.get("rerank_score"),
            "final_score_type": ctx.get("final_score_type"),
        })


    return {
        "contexts": contexts,
        "citations": citations,
        "retrieval_metadata": retrieval_result.get("metadata", {}),
    }
