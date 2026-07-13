from __future__ import annotations

from app.rag.online_hybrid_retriever import (
    OnlineHybridRetriever,
    build_online_hybrid_retriever,
)


class IndustrialRetriever:
    def __init__(
        self,
        hybrid_retriever: OnlineHybridRetriever | None = None,
    ):
        self.hybrid_retriever = (
            hybrid_retriever or build_online_hybrid_retriever()
        )

    def retrieve(self, question: str, top_k: int = 5) -> list[dict]:
        return self.retrieve_with_metadata(question, top_k)["contexts"]

    def retrieve_with_metadata(self, question: str, top_k: int = 5) -> dict:
        return self.hybrid_retriever.retrieve(
            question=question,
            top_k=top_k,
            vector_top_k=max(top_k * 4, 20),
            keyword_top_k=max(top_k * 4, 20),
            rerank_candidate_k=max(top_k * 4, 20),
        )
