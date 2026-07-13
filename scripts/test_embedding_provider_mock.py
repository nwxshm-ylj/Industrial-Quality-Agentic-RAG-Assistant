from app.rag.embeddings.factory import (
    clear_embedding_provider_cache,
    get_embedding_provider,
    set_embedding_provider_for_testing,
)
from app.rag.embeddings.mock_provider import MockEmbeddingProvider


def main() -> None:
    provider = MockEmbeddingProvider(dimension=12)
    set_embedding_provider_for_testing(provider)
    try:
        resolved = get_embedding_provider()
        assert resolved is provider
        assert get_embedding_provider() is resolved

        documents = resolved.embed_documents(["工业质量", "轮毂识别"])
        query = resolved.embed_query("工业质量")
        assert len(documents) == 2
        assert all(len(vector) == 12 for vector in documents)
        assert len(query) == 12
        assert documents[0] != query, "query/document semantics must differ"
        assert documents == resolved.embed_documents(["工业质量", "轮毂识别"])
        print("Mock EmbeddingProvider tests passed")
    finally:
        set_embedding_provider_for_testing(None)
        clear_embedding_provider_cache()


if __name__ == "__main__":
    main()
