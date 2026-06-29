from app.graph.state import IndustrialRAGState
from app.rag.retriever import IndustrialRetriever


retriever = IndustrialRetriever()


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

    print("=" * 80)
    print("retrieve_node 检索完成")
    print("原始问题:", question)
    print("实际检索 query:", rewritten_query)
    print("contexts 数量:", len(contexts))

    for ctx in contexts:
        print(
            ctx.get("source"),
            "score:", ctx.get("score"),
            "retrieval_source:", ctx.get("retrieval_source"),
            "vector_score:", ctx.get("vector_score"),
            "bm25_score:", ctx.get("bm25_score"),
            "hybrid_score:", ctx.get("hybrid_score"),
            "rerank_score:", ctx.get("rerank_score"),
            "final_score_type:", ctx.get("final_score_type"),
        )

    print("=" * 80)

    return {
        "contexts": contexts,
        "citations": citations
    }