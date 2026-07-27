from app.rag.search_backends.base import VectorSearchError
from app.rag.retriever import IndustrialRetriever


class _FakeHybridRetriever:
    def retrieve(self, **kwargs) -> dict:
        return {
            "contexts": [
                {
                    "doc_id": "text-doc",
                    "chunk_id": "text-doc-0",
                    "text": "wheel recognition troubleshooting",
                    "source": "manual.txt",
                    "score": 0.8,
                    "retrieval_source": "vector+keyword",
                }
            ],
            "metadata": {"retrieval_mode": "hybrid"},
        }


class _FakeMultimodalRetriever:
    collection_alias = "industrial_multimodal_active"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.queries = []

    def search(self, query, top_k, *, filters=None):
        self.queries.append(query)
        if self.fail:
            raise VectorSearchError("multimodal alias unavailable")
        return [
            {
                "doc_id": "image-doc",
                "asset_id": "image-doc-page-1",
                "text": "camera exposure diagram",
                "source": "camera.pdf",
                "modality": "text+image",
                "score": 0.9,
                "retrieval_source": "multimodal_vector",
            }
        ]


def main() -> None:
    multimodal = _FakeMultimodalRetriever()
    retriever = IndustrialRetriever(
        hybrid_retriever=_FakeHybridRetriever(),
        multimodal_retriever=multimodal,
        multimodal_enabled=True,
        multimodal_rrf_k=60,
        multimodal_degraded_mode="text_only",
    )
    result = retriever.retrieve_with_metadata(
        "find a similar camera fault",
        top_k=5,
        multimodal_query={
            "images": ["data:image/png;base64,AAAA"],
        },
    )
    assert len(result["contexts"]) == 2
    assert result["metadata"]["multimodal_requested"] is True
    assert result["metadata"]["multimodal_degraded"] is False
    assert result["contexts"][0]["final_score_type"] == "cross_modal_rrf_score"
    assert multimodal.queries[0].text == "find a similar camera fault"

    degraded = IndustrialRetriever(
        hybrid_retriever=_FakeHybridRetriever(),
        multimodal_retriever=_FakeMultimodalRetriever(fail=True),
        multimodal_enabled=True,
        multimodal_rrf_k=60,
        multimodal_degraded_mode="text_only",
    ).retrieve_with_metadata(
        "find a similar camera fault",
        multimodal_query={"images": ["data:image/png;base64,AAAA"]},
    )
    assert degraded["metadata"]["multimodal_degraded"] is True
    assert len(degraded["contexts"]) == 1

    disabled = IndustrialRetriever(
        hybrid_retriever=_FakeHybridRetriever(),
        multimodal_enabled=False,
        multimodal_rrf_k=60,
        multimodal_degraded_mode="text_only",
    ).retrieve_with_metadata(
        "text remains available",
        multimodal_query={"images": ["data:image/png;base64,AAAA"]},
    )
    assert disabled["metadata"]["multimodal_degraded"] is True

    print("Multimodal retrieval fusion/degradation tests passed without API calls")


if __name__ == "__main__":
    main()
