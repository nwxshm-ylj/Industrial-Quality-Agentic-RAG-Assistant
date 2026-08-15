from app.rag.embeddings.mock_provider import MockEmbeddingProvider
from app.rag.online_hybrid_retriever import OnlineHybridRetriever
from app.rag.search_backends.base import KeywordSearchError


class _VectorBackend:
    def __init__(self, provider: MockEmbeddingProvider) -> None:
        self.provider = provider

    def search(self, query: str, top_k: int = 5, *, filters=None) -> list[dict]:
        self.filters = filters
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

    def search(self, query: str, top_k: int = 5, *, filters=None) -> list[dict]:
        self.filters = filters
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

    def get_adjacent_chunks(self, seeds, *, window=1):
        self.neighbor_seeds = seeds
        self.neighbor_window = window
        return [
            {
                "chunk_id": "neighbor-1",
                "doc_id": seeds[0].get("doc_id"),
                "chunk_index": 2,
                "text": "adjacent evidence",
                "source": "quality.md",
                "score": 1.0,
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

    filtered = OnlineHybridRetriever(
        vector,
        _KeywordBackend(),
        use_reranker=False,
    ).retrieve(
        "quality",
        top_k=2,
        filters={"doc_types": ["FMEA"]},
    )
    assert filtered["metadata"]["filters_applied"] == {
        "doc_types": ["FMEA"]
    }

    neighbor_vector = _VectorBackend(provider)
    neighbor_vector.search = lambda query, top_k=5, filters=None: [
        {
            "chunk_id": "seed-1",
            "doc_id": "doc-1",
            "chunk_index": 1,
            "text": "chapter overview",
            "source": "quality.md",
            "score": 0.9,
            "retrieval_source": "vector",
        },
        {
            "chunk_id": "seed-2",
            "doc_id": "doc-2",
            "chunk_index": 5,
            "text": "other evidence",
            "source": "other.md",
            "score": 0.8,
            "retrieval_source": "vector",
        },
    ][:top_k]
    neighbor_keyword = _KeywordBackend()
    expanded = OnlineHybridRetriever(
        neighbor_vector,
        neighbor_keyword,
        use_reranker=False,
        neighbor_expansion_enabled=True,
        neighbor_seed_k=1,
    ).retrieve("quality", top_k=2)
    assert [item["chunk_id"] for item in expanded["contexts"]] == [
        "seed-1",
        "neighbor-1",
    ]
    assert expanded["contexts"][1]["final_score_type"] == "adjacent_context"
    assert expanded["metadata"]["neighbor_added_count"] == 1
    assert OnlineHybridRetriever._metadata_query_overlap(
        "车身尺寸管理输入",
        {"source": "整车制造过程_标准化管理手册_车身尺寸模块_2022.pdf"},
    ) > OnlineHybridRetriever._metadata_query_overlap(
        "车身尺寸管理输入",
        {"source": "整车制造过程_标准化管理手册_扭矩_2.1.pdf"},
    )

    class _FailingReranker:
        def rerank(self, **kwargs):
            raise RuntimeError("reranker timeout")

    reranker_degraded = OnlineHybridRetriever(
        vector,
        _KeywordBackend(),
        use_reranker=True,
        reranker=_FailingReranker(),
        reranker_fail_open=True,
    ).retrieve("quality", top_k=2)
    assert reranker_degraded["metadata"]["degraded"] is True
    assert reranker_degraded["metadata"]["reranker_degraded"] is True
    assert "reranker" in reranker_degraded["metadata"]["degraded_components"]
    assert reranker_degraded["contexts"]
    print("Online hybrid retrieval and vector-only degradation tests passed")


if __name__ == "__main__":
    main()
