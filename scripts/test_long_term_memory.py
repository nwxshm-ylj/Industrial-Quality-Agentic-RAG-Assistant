from types import SimpleNamespace

from app.memory.long_term import HybridLongTermMemoryStore
from app.rag.embeddings.mock_provider import MockEmbeddingProvider


class _Models:
    class Distance:
        COSINE = "Cosine"

    @staticmethod
    def _value(kind, **kwargs):
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
    def PointIdsList(cls, **kwargs):
        return cls._value("PointIdsList", **kwargs)


class _Qdrant:
    def __init__(self) -> None:
        self.dimension = None
        self.points = []
        self.deletes = []

    def collection_exists(self, name):
        return self.dimension is not None

    def create_collection(self, *, collection_name, vectors_config):
        self.dimension = vectors_config.size

    def get_collection(self, name):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=self.dimension))
            )
        )

    def upsert(self, *, collection_name, points, wait):
        self.points.extend(points)

    def delete(self, **kwargs):
        self.deletes.append(kwargs)

    def query_points(self, **kwargs):
        return SimpleNamespace(
            points=[
                SimpleNamespace(payload=self.points[0].payload, score=0.88)
            ]
        )


class _Indices:
    def __init__(self) -> None:
        self.created = False

    def exists(self, index):
        return self.created

    def create(self, *, index, body):
        self.created = True


class _OpenSearch:
    def __init__(self) -> None:
        self.indices = _Indices()
        self.documents = {}

    def index(self, *, index, id, body, refresh):
        self.documents[id] = body

    def search(self, *, index, body):
        memory_id, document = next(iter(self.documents.items()))
        return {
            "hits": {
                "hits": [
                    {"_id": memory_id, "_score": 2.0, "_source": document}
                ]
            }
        }


def main() -> None:
    qdrant = _Qdrant()
    opensearch = _OpenSearch()
    store = HybridLongTermMemoryStore(
        MockEmbeddingProvider(dimension=8),
        qdrant_client=qdrant,
        opensearch_client=opensearch,
        collection_name="memory_v1",
        index_name="memory_keyword_v1",
        models_module=_Models,
    )
    memory_id = store.save_interaction(
        owner_key="engineer-a",
        session_id="session-1",
        question="Wheel recognition is abnormal",
        answer="Check camera exposure and calibration first.",
        intent="fault_diagnosis",
    )
    assert memory_id
    assert qdrant.points[0].payload["owner_key"] == "engineer-a"
    assert opensearch.documents[memory_id]["session_id"] == "session-1"
    results = store.search(
        owner_key="engineer-a",
        query="camera calibration",
        limit=3,
    )
    assert len(results) == 1
    assert results[0]["memory_id"] == memory_id
    assert results[0]["retrieval_source"] == "keyword+vector"
    assert results[0]["final_score_type"] == "rrf_score"
    print("Long-term hybrid memory tests passed with mock backends")


if __name__ == "__main__":
    main()
