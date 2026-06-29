from app.core.config import settings
from app.rag.vectorstore import QdrantVectorStore
from app.rag.bm25_retriever import BM25Retriever
from app.rag.reranker import IndustrialReranker


class HybridRetriever:
    def __init__(self):
        self.vectorstore = QdrantVectorStore()
        self.bm25_retriever = BM25Retriever()

        self.use_reranker = settings.use_reranker
        self.reranker = None

        if self.use_reranker:
            try:
                self.reranker = IndustrialReranker()
                print("Reranker 加载成功:", settings.reranker_model)
            except Exception as e:
                print("Reranker 加载失败，将退回 Hybrid Search:", repr(e))
                self.use_reranker = False
                self.reranker = None

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        vector_top_k: int = 20,
        bm25_top_k: int = 20,
        vector_weight: float = 0.65,
        bm25_weight: float = 0.35,
        min_score: float = 0.15,
        rerank_candidate_k: int = 20,
    ) -> list[dict]:
        vector_results = self._vector_search(
            question=question,
            top_k=vector_top_k
        )

        bm25_results = self.bm25_retriever.retrieve(
            query=question,
            top_k=bm25_top_k
        )

        merged_results = self._merge_results(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )

        filtered_results = [
            item for item in merged_results
            if item.get("hybrid_score", 0.0) >= min_score
        ]

        candidates = filtered_results[:rerank_candidate_k]

        if self.use_reranker and self.reranker is not None and candidates:
            reranked_results = self.reranker.rerank(
                question=question,
                documents=candidates,
                top_k=top_k,
            )

            for item in reranked_results:
                item["score"] = item.get("rerank_score")
                item["final_score_type"] = "rerank_score"

            return reranked_results

        for item in candidates:
            item["final_score_type"] = "hybrid_score"

        return candidates[:top_k]

    def _vector_search(self, question: str, top_k: int) -> list[dict]:
        results = self.vectorstore.search(
            query=question,
            top_k=top_k
        )

        documents = []

        for result in results:
            payload = result.payload or {}

            documents.append({
                "text": payload.get("text", ""),
                "source": payload.get("source", ""),
                "doc_type": payload.get("doc_type", ""),
                "chunk_id": payload.get("chunk_id", ""),
                "score": float(result.score),
                "retrieval_source": "vector",
            })

        return documents

    def _merge_results(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        vector_weight: float,
        bm25_weight: float,
    ) -> list[dict]:
        normalized_vector = self._normalize_scores(vector_results)
        normalized_bm25 = self._normalize_scores(bm25_results)

        merged = {}

        for item in normalized_vector:
            chunk_key = self._get_chunk_key(item)

            if chunk_key not in merged:
                merged[chunk_key] = {
                    **item,
                    "vector_score": 0.0,
                    "bm25_score": 0.0,
                    "hybrid_score": 0.0,
                    "retrieval_sources": set(),
                }

            merged[chunk_key]["vector_score"] = item["normalized_score"]
            merged[chunk_key]["retrieval_sources"].add("vector")

        for item in normalized_bm25:
            chunk_key = self._get_chunk_key(item)

            if chunk_key not in merged:
                merged[chunk_key] = {
                    **item,
                    "vector_score": 0.0,
                    "bm25_score": 0.0,
                    "hybrid_score": 0.0,
                    "retrieval_sources": set(),
                }

            merged[chunk_key]["bm25_score"] = item["normalized_score"]
            merged[chunk_key]["retrieval_sources"].add("bm25")

        final_results = []

        for item in merged.values():
            hybrid_score = (
                vector_weight * item.get("vector_score", 0.0)
                + bm25_weight * item.get("bm25_score", 0.0)
            )

            item["hybrid_score"] = hybrid_score
            item["score"] = hybrid_score
            item["retrieval_source"] = "+".join(sorted(item["retrieval_sources"]))

            item.pop("retrieval_sources", None)
            item.pop("normalized_score", None)

            final_results.append(item)

        final_results.sort(
            key=lambda x: x.get("hybrid_score", 0.0),
            reverse=True
        )

        return final_results

    def _normalize_scores(self, results: list[dict]) -> list[dict]:
        if not results:
            return []

        scores = [
            float(item.get("score", 0.0))
            for item in results
        ]

        min_score = min(scores)
        max_score = max(scores)

        normalized_results = []

        for item in results:
            raw_score = float(item.get("score", 0.0))

            if max_score == min_score:
                normalized_score = 1.0
            else:
                normalized_score = (raw_score - min_score) / (max_score - min_score)

            normalized_results.append({
                **item,
                "raw_score": raw_score,
                "normalized_score": normalized_score,
            })

        return normalized_results

    def _get_chunk_key(self, item: dict) -> str:
        chunk_id = item.get("chunk_id")

        if chunk_id:
            return chunk_id

        source = item.get("source", "")
        text = item.get("text", "")

        return f"{source}_{hash(text)}"