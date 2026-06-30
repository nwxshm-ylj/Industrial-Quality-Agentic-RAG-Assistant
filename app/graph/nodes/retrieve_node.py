from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.rag.retriever import IndustrialRetriever


retriever = IndustrialRetriever()


@observe_node("retrieve")
def retrieve_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    rewritten_query = state.get("rewritten_query") or question
    top_k = state.get("top_k", 5)

    contexts = retriever.retrieve(
        question=rewritten_query,
        top_k=top_k
    )

    citations = []

    for ctx in contexts:
        citations.append({
            "source": ctx.get("source"),
            "doc_type": ctx.get("doc_type"),
            "chunk_id": ctx.get("chunk_id"),
            "score": ctx.get("score"),
            "retrieval_source": ctx.get("retrieval_source"),
            "vector_score": ctx.get("vector_score"),
            "bm25_score": ctx.get("bm25_score"),
            "hybrid_score": ctx.get("hybrid_score"),
            "rerank_score": ctx.get("rerank_score"),
            "final_score_type": ctx.get("final_score_type"),
        })


    return {
        "contexts": contexts,
        "citations": citations
    }