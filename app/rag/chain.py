from app.rag.retriever import IndustrialRetriever
from app.rag.generator import AnswerGenerator


class IndustrialRAGChain:
    def __init__(self):
        self.retriever = IndustrialRetriever()
        self.generator = AnswerGenerator()

    def invoke(self, question: str, top_k: int = 5) -> dict:
        contexts = self.retriever.retrieve(question, top_k=top_k)

        answer = self.generator.generate(
            question=question,
            contexts=contexts
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
    })

        return {
            "question": question,
            "answer": answer,
            "citations": citations
        }