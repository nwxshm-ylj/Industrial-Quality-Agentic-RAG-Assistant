from app.multimodal.base import MultimodalEmbeddingDimensionError
from app.multimodal.factory import (
    clear_multimodal_embedding_provider_cache,
    get_multimodal_embedding_provider,
    set_multimodal_embedding_provider_for_testing,
)
from app.multimodal.mock_provider import MockMultimodalEmbeddingProvider
from app.multimodal.qwen_provider import QwenMultimodalEmbeddingProvider
from app.multimodal.types import MultimodalEmbeddingInput


class _FakeResponse:
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "output": {
                "embeddings": [
                    {
                        "index": 0,
                        "type": "fusion",
                        "embedding": [0.25] * self.dimension,
                    }
                ]
            },
            "usage": {"input_tokens": 8},
        }


class _FakeClient:
    def __init__(self, dimension: int, calls: list[dict]) -> None:
        self.dimension = dimension
        self.calls = calls

    def post(self, url: str, *, json: dict, timeout: tuple) -> _FakeResponse:
        self.calls.append({"url": url, "payload": json, "timeout": timeout})
        return _FakeResponse(self.dimension)


def main() -> None:
    calls: list[dict] = []
    provider = QwenMultimodalEmbeddingProvider(
        api_key="test-key",
        endpoint="https://example.invalid/multimodal",
        dimension=1024,
        client=_FakeClient(1024, calls),
    )
    document = MultimodalEmbeddingInput(
        text="wheel OCR content",
        images=("data:image/png;base64,AAAA",),
    )
    query = MultimodalEmbeddingInput(text="find wheel recognition diagrams")
    assert len(provider.embed_documents([document])[0]) == 1024
    assert len(provider.embed_query(query)) == 1024
    document_payload = calls[0]["payload"]
    query_payload = calls[1]["payload"]
    assert document_payload["parameters"]["enable_fusion"] is True
    assert document_payload["parameters"]["dimension"] == 1024
    assert "document" in document_payload["parameters"]["instruct"]
    assert "search query" in query_payload["parameters"]["instruct"]
    assert provider.dimension_validated is True

    invalid = QwenMultimodalEmbeddingProvider(
        api_key="test-key",
        endpoint="https://example.invalid/multimodal",
        dimension=1024,
        client=_FakeClient(8, []),
    )
    try:
        invalid.embed_query(query)
    except MultimodalEmbeddingDimensionError:
        pass
    else:
        raise AssertionError("dimension mismatch must fail fast")

    mock = MockMultimodalEmbeddingProvider(dimension=8)
    set_multimodal_embedding_provider_for_testing(mock)
    try:
        assert get_multimodal_embedding_provider() is mock
        assert get_multimodal_embedding_provider() is mock
        assert len(mock.embed_query(query)) == 8
    finally:
        set_multimodal_embedding_provider_for_testing(None)
        clear_multimodal_embedding_provider_cache()

    print("Multimodal EmbeddingProvider tests passed without network access")


if __name__ == "__main__":
    main()
