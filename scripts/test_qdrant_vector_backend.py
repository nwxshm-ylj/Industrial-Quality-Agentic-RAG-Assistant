from types import SimpleNamespace

from app.rag.embeddings.base import EmbeddingDimensionError
from app.rag.embeddings.mock_provider import MockEmbeddingProvider
from app.rag.search_backends.qdrant_backend import QdrantVectorSearchBackend


class _Models:
    class Distance:
        COSINE = "Cosine"

    @staticmethod
    def _value(kind: str, **kwargs):
        return SimpleNamespace(kind=kind, **kwargs)

    @classmethod
    def VectorParams(cls, **kwargs):
        return cls._value("VectorParams", **kwargs)

    @classmethod
    def PointStruct(cls, **kwargs):
        return cls._value("PointStruct", **kwargs)

    @classmethod
    def FieldCondition(cls, **kwargs):
        return cls._value("FieldCondition", **kwargs)

    @classmethod
    def MatchValue(cls, **kwargs):
        return cls._value("MatchValue", **kwargs)

    @classmethod
    def Filter(cls, **kwargs):
        return cls._value("Filter", **kwargs)

    @classmethod
    def FilterSelector(cls, **kwargs):
        return cls._value("FilterSelector", **kwargs)

    @classmethod
    def DeleteAlias(cls, **kwargs):
        return cls._value("DeleteAlias", **kwargs)

    @classmethod
    def DeleteAliasOperation(cls, **kwargs):
        return cls._value("DeleteAliasOperation", **kwargs)

    @classmethod
    def CreateAlias(cls, **kwargs):
        return cls._value("CreateAlias", **kwargs)

    @classmethod
    def CreateAliasOperation(cls, **kwargs):
        return cls._value("CreateAliasOperation", **kwargs)


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.collections = {}
        self.aliases = []
        self.upserts = []
        self.deletes = []
        self.payload_updates = []
        self.queries = []
        self.indexed_count = 1

    def collection_exists(self, name):
        return name in self.collections

    def create_collection(self, *, collection_name, vectors_config):
        self.collections[collection_name] = vectors_config.size

    def get_collection(self, name):
        size = self.collections[name]
        vectors = SimpleNamespace(size=size)
        return SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(vectors=vectors))
        )

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)

    def delete(self, **kwargs):
        self.deletes.append(kwargs)

    def set_payload(self, **kwargs):
        self.payload_updates.append(kwargs)

    def query_points(self, **kwargs):
        self.queries.append(kwargs)
        point = SimpleNamespace(
            payload={
                "doc_id": "d1",
                "chunk_id": "d1_0",
                "text": "工业质量",
                "source": "test.txt",
                "doc_type": "TEST",
            },
            score=0.9,
        )
        return SimpleNamespace(points=[point])

    def count(self, **kwargs):
        return SimpleNamespace(count=self.indexed_count)

    def get_aliases(self):
        return SimpleNamespace(aliases=self.aliases)

    def update_collection_aliases(self, *, change_aliases_operations):
        self.aliases = [
            SimpleNamespace(
                alias_name="industrial_docs_active",
                collection_name="industrial_docs_qwen_1024_v1",
            )
        ]


class _WrongDimensionProvider(MockEmbeddingProvider):
    def embed_documents(self, texts):
        return [[0.0, 1.0] for _ in texts]


def main() -> None:
    client = _FakeQdrantClient()
    provider = MockEmbeddingProvider(
        dimension=4,
        model_name="text-embedding-v4",
        index_version="qwen-1024-v1",
    )
    backend = QdrantVectorSearchBackend(
        provider,
        collection_name="industrial_docs_qwen_1024_v1",
        collection_alias="industrial_docs_active",
        client=client,
        models_module=_Models,
    )
    chunks = [
        {
            "text": "工业质量",
            "metadata": {
                "chunk_id": "d1_0",
                "chunk_index": 0,
                "source": "test.txt",
                "doc_type": "TEST",
                "version": "v1",
            },
        }
    ]

    backend.upsert_document_chunks("d1", chunks)
    point = client.upserts[0]["points"][0]
    assert client.upserts[0]["collection_name"] == backend.collection_name
    assert point.payload["embedding_provider"] == "mock"
    assert point.payload["embedding_dimension"] == 4
    assert point.payload["embedding_index_version"] == "qwen-1024-v1"

    backend.activate_alias()
    results = backend.search("质量", top_k=3)
    assert client.queries[0]["collection_name"] == "industrial_docs_active"
    assert results[0]["chunk_id"] == "d1_0"
    assert backend.count_indexed() == 1

    backend.delete_by_doc_id("d1")
    assert client.deletes[0]["collection_name"] == backend.collection_name
    backend.delete_all_except_operation("migration-1")
    assert client.deletes[1]["collection_name"] == backend.collection_name
    backend.set_document_index_status(
        "d1",
        "indexed",
        index_operation_id="operation-1",
    )
    assert client.payload_updates[0]["payload"] == {"index_status": "indexed"}

    wrong = QdrantVectorSearchBackend(
        _WrongDimensionProvider(dimension=4),
        collection_name="industrial_docs_qwen_1024_v1",
        collection_alias="industrial_docs_active",
        client=client,
        models_module=_Models,
    )
    before = len(client.upserts)
    try:
        wrong.upsert_document_chunks("d2", chunks)
    except EmbeddingDimensionError:
        pass
    else:
        raise AssertionError("wrong vector dimensions must fail before Qdrant upsert")
    assert len(client.upserts) == before
    assert not hasattr(client, "delete_collection")
    print("Qdrant vector backend tests passed with MockEmbeddingProvider")


if __name__ == "__main__":
    main()
