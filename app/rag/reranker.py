from typing import Any

from sentence_transformers import CrossEncoder

from app.core.config import settings


class IndustrialReranker:
    def __init__(self):
        self.model_name = settings.reranker_model
        self.model = CrossEncoder(self.model_name)

    def rerank(
        self,
        question: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not documents:
            return []

        pairs = [
            [question, doc.get("text", "")]
            for doc in documents
        ]

        scores = self.model.predict(pairs)

        reranked_docs = []

        for doc, score in zip(documents, scores):
            reranked_docs.append({
                **doc,
                "rerank_score": float(score),
            })

        reranked_docs.sort(
            key=lambda x: x.get("rerank_score", 0.0),
            reverse=True
        )

        return reranked_docs[:top_k]