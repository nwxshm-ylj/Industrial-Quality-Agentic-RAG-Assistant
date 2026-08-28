from types import SimpleNamespace

from app.multimodal.mock_provider import MockMultimodalEmbeddingProvider
from app.multimodal.types import MultimodalEmbeddingInput
from app.rag.search_backends.base import VectorSearchError
from app.rag.retrieval_filters import RetrievalFilter
from app.rag.search_backends.multimodal_qdrant_backend import (
    MultimodalQdrantSearchBackend,
)


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
    def MatchAny(cls, **kwargs):
        return cls._value("MatchAny", **kwargs)

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
        vectors = SimpleNamespace(size=self.collections[name])
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
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    payload={
                        "doc_id": "d1",
                        "asset_id": "d1_page_1",
                        "text": "wheel inspection image",
                        "source": "wheel.pdf",
                        "modality": "text+image",
                        "page_number": 1,
                    },
                    score=0.91,
                )
            ]
        )

    def count(self, **kwargs):
        return SimpleNamespace(count=self.indexed_count)

    def get_aliases(self):
        return SimpleNamespace(aliases=self.aliases)

    def update_collection_aliases(self, *, change_aliases_operations):
        self.aliases = [
            SimpleNamespace(
                alias_name="industrial_multimodal_active",
                collection_name="industrial_multimodal_qwen3vl_1024_v1",
            )
        ]


def main() -> None:
    client = _FakeQdrantClient()
    provider = MockMultimodalEmbeddingProvider(dimension=8)
    backend = MultimodalQdrantSearchBackend(
        provider,
        collection_name="industrial_multimodal_qwen3vl_1024_v1",
        collection_alias="industrial_multimodal_active",
        client=client,
        models_module=_Models,
    )
    backend.upsert_document_assets(
        "d1",
        [
            {
                "text": "wheel inspection image",
                "embedding_input": MultimodalEmbeddingInput(
                    text="wheel inspection image",
                    images=("data:image/png;base64,AAAA",),
                ),
                "metadata": {
                    "asset_id": "d1_page_1",
                    "page_number": 1,
                    "source": "wheel.pdf",
                    "doc_type": "manual",
                    "version": "v1",
                    "asset_path": "data/uploads/assets/d1/page_1.png",
                },
            }
        ],
    )
    point = client.upserts[0]["points"][0]
    assert client.upserts[0]["collection_name"] == backend.collection_name
    assert point.payload["embedding_model"] == provider.model_name
    assert point.payload["embedding_dimension"] == 8
    assert point.payload["asset_id"] == "d1_page_1"
    backend.set_document_index_status(
        "d1",
        "indexed",
        index_operation_id="operation-1",
    )
    assert client.payload_updates[0]["payload"] == {"index_status": "indexed"}

    backend.activate_alias()
    results = backend.search(MultimodalEmbeddingInput(text="wheel"))
    assert client.queries[0]["collection_name"] == backend.collection_alias
    assert results[0]["modality"] == "text+image"
    backend.search(
        MultimodalEmbeddingInput(text="door"),
        filters=RetrievalFilter(
            vehicle_models=("tiguan",),
            components=("door",),
        ),
    )
    assert [
        condition.key for condition in client.queries[1]["query_filter"].must
    ] == ["index_status", "vehicle_models", "components"]
    backend.delete_by_doc_id("d1")
    assert client.deletes[0]["collection_name"] == backend.collection_name
    assert not hasattr(client, "delete_collection")

    empty_client = _FakeQdrantClient()
    empty_client.collections[backend.collection_name] = 8
    empty_client.indexed_count = 0
    empty_backend = MultimodalQdrantSearchBackend(
        provider,
        collection_name=backend.collection_name,
        collection_alias=backend.collection_alias,
        client=empty_client,
        models_module=_Models,
    )
    try:
        empty_backend.activate_alias()
    except VectorSearchError:
        pass
    else:
        raise AssertionError("empty index must not activate the alias")

    print("Multimodal Qdrant backend tests passed without network access")


if __name__ == "__main__":
    main()
