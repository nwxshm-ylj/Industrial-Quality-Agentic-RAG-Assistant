from __future__ import annotations

import tempfile
from pathlib import Path

from app.rag.embeddings.base import (
    EmbeddingDimensionError,
    EmbeddingProviderError,
)
from app.rag.embeddings.local_provider import (
    LocalSentenceTransformerEmbeddingProvider,
)


class _FakeModel:
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension
        self.calls: list[dict] = []

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, sentences: list[str], **kwargs):
        self.calls.append({"sentences": list(sentences), **kwargs})
        return [
            [float(index + 1)] * self.dimension
            for index, _sentence in enumerate(sentences)
        ]


def main() -> None:
    model = _FakeModel(4)
    provider = LocalSentenceTransformerEmbeddingProvider(
        model_path="unused-in-test",
        model_name="BAAI/bge-m3",
        dimension=4,
        batch_size=2,
        model=model,
        index_version="bge-m3-test-v1",
    )
    documents = provider.embed_documents(["工业质量", "设备诊断"])
    query = provider.embed_query("轮毂识别异常")
    assert len(documents) == 2 and len(documents[0]) == 4
    assert len(query) == 4
    assert model.calls[0]["batch_size"] == 2
    assert model.calls[0]["normalize_embeddings"] is True
    assert model.calls[0]["convert_to_numpy"] is True
    assert model.calls[1]["sentences"] == ["轮毂识别异常"]

    try:
        LocalSentenceTransformerEmbeddingProvider(
            model_path="unused-in-test",
            dimension=4,
            model=_FakeModel(3),
        )
    except EmbeddingDimensionError:
        pass
    else:
        raise AssertionError("model dimension mismatch must fail at startup")

    with tempfile.TemporaryDirectory() as directory:
        missing = Path(directory) / "missing-bge-m3"
        try:
            LocalSentenceTransformerEmbeddingProvider(model_path=missing)
        except EmbeddingProviderError:
            pass
        else:
            raise AssertionError("missing local model must fail without download")

    print("Local BGE-M3 EmbeddingProvider tests passed without model loading")


if __name__ == "__main__":
    main()
