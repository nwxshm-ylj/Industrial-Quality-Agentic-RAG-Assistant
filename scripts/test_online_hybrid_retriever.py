from app.rag.embeddings.mock_provider import MockEmbeddingProvider
from app.rag.online_hybrid_retriever import OnlineHybridRetriever
from app.rag.search_backends.base import KeywordSearchError


class _VectorBackend:
    def __init__(self, provider: MockEmbeddingProvider) -> None:
        self.provider = provider

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        self.provider.embed_query(query)
        return [
            {
                "chunk_id": "shared",
                "text": "轮毂识别异常检查曝光",
                "source": "quality.md",
                "score": 0.9,
                "retrieval_source": "vector",
            },
            {
                "chunk_id": "vector-only",
                "text": "相机标定",
                "source": "camera.md",
                "score": 0.8,
                "retrieval_source": "vector",
            },
        ][:top_k]


class _KeywordBackend:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if self.fail:
            raise KeywordSearchError("OpenSearch unavailable")
        return [
            {
                "chunk_id": "shared",
                "text": "轮毂识别异常检查曝光",
                "source": "quality.md",
                "score": 7.5,
                "retrieval_source": "keyword",
            }
        ]


def main() -> None:
    provider = MockEmbeddingProvider(dimension=16)
    vector = _VectorBackend(provider)

    hybrid = OnlineHybridRetriever(
        vector,
        _KeywordBackend(),
        use_reranker=False,
    ).retrieve("轮毂异常", top_k=2)
    assert hybrid["metadata"]["degraded"] is False
    assert hybrid["metadata"]["retrieval_mode"] == "hybrid"
    assert hybrid["contexts"][0]["chunk_id"] == "shared"
    assert hybrid["contexts"][0]["keyword_score"] == 7.5
    assert hybrid["contexts"][0]["bm25_score"] == 7.5
    assert hybrid["contexts"][0]["rrf_score"] > 0

    degraded = OnlineHybridRetriever(
        vector,
        _KeywordBackend(fail=True),
        degraded_mode="vector_only",
        use_reranker=False,
    ).retrieve("轮毂异常", top_k=2)
    assert degraded["metadata"]["degraded"] is True
    assert degraded["metadata"]["retrieval_mode"] == "vector_only"
    assert "OpenSearch unavailable" in degraded["metadata"]["degraded_reason"]
    assert degraded["contexts"]
    print("Online hybrid retrieval and vector-only degradation tests passed")


if __name__ == "__main__":
    main()
