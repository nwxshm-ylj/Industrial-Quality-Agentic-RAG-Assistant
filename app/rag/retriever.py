from app.rag.hybrid_retriever import HybridRetriever


class IndustrialRetriever:
    def __init__(self):
        self.hybrid_retriever = HybridRetriever()

    def retrieve(self, question: str, top_k: int = 5) -> list[dict]:
        return self.hybrid_retriever.retrieve(
            question=question,
            top_k=top_k,
            vector_top_k=max(top_k * 4, 20),
            bm25_top_k=max(top_k * 4, 20),
            rerank_candidate_k=max(top_k * 4, 20),
        )