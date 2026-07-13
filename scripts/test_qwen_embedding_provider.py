from app.rag.embeddings.base import EmbeddingDimensionError
from app.rag.embeddings.qwen_provider import QwenEmbeddingProvider


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _FakeClient:
    def __init__(self, dimension: int, calls: list[dict]) -> None:
        self.dimension = dimension
        self.calls = calls

    def post(self, url: str, *, json: dict, timeout: tuple) -> _FakeResponse:
        self.calls.append(json)
        texts = json["input"]["texts"]
        return _FakeResponse(
            {
                "output": {
                    "embeddings": [
                        {
                            "text_index": index,
                            "embedding": [float(index + 1)] * self.dimension,
                        }
                        for index, _ in enumerate(texts)
                    ]
                }
            }
        )


def _client_for_dimension(dimension: int, calls: list[dict]) -> _FakeClient:
    return _FakeClient(dimension, calls)


def main() -> None:
    calls: list[dict] = []
    provider = QwenEmbeddingProvider(
        api_key="test-key",
        dimension=1024,
        endpoint="https://example.invalid/embedding",
        client=_client_for_dimension(1024, calls),
    )

    documents = provider.embed_documents(["文档一", "文档二"])
    query = provider.embed_query("查询")
    assert len(documents) == 2 and len(documents[0]) == 1024
    assert len(query) == 1024
    assert calls[0]["parameters"]["text_type"] == "document"
    assert calls[1]["parameters"]["text_type"] == "query"
    assert provider.dimension_validated is True

    invalid_provider = QwenEmbeddingProvider(
        api_key="test-key",
        dimension=1024,
        endpoint="https://example.invalid/embedding",
        client=_client_for_dimension(8, []),
    )
    try:
        invalid_provider.embed_documents(["dimension mismatch"])
    except EmbeddingDimensionError:
        pass
    else:
        raise AssertionError("dimension mismatch must fail before indexing")

    print("Qwen EmbeddingProvider adapter tests passed without network access")


if __name__ == "__main__":
    main()
