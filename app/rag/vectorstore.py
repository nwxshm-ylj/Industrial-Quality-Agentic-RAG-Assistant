from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class QdrantVectorStore:
    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url)
        self.model = SentenceTransformer(settings.embedding_model)
        # Legacy BM25/BGE ingestion is isolated from online Qwen collections.
        self.collection_name = settings.legacy_qdrant_collection

    def _create_collection_if_missing(self) -> None:
        if self.client.collection_exists(self.collection_name):
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.model.get_sentence_embedding_dimension(),
                distance=Distance.COSINE,
            ),
        )

    def recreate_collection(self):
        vector_size = self.model.get_sentence_embedding_dimension()

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )

    def add_chunks(self, chunks: list[dict]):
        texts = [chunk["text"] for chunk in chunks]
        vectors = self.model.encode(texts, normalize_embeddings=True)

        points = []

        for idx, chunk in enumerate(chunks):
            points.append(
                PointStruct(
                    id=idx,
                    vector=vectors[idx].tolist(),
                    payload={
                        "text": chunk["text"],
                        **chunk["metadata"]
                    }
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def add_document_chunks(
        self,
        doc_id: str,
        chunks: list[dict],
    ) -> None:
        if not chunks:
            return

        self._create_collection_if_missing()
        texts = [chunk["text"] for chunk in chunks]
        vectors = self.model.encode(texts, normalize_embeddings=True)
        points = []

        for index, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            chunk_id = metadata.get("chunk_id") or f"{doc_id}_{index}"
            point_id = str(uuid5(NAMESPACE_URL, f"{doc_id}:{chunk_id}"))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vectors[index].tolist(),
                    payload={
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "text": chunk["text"],
                        "source": metadata.get("source"),
                        "doc_type": metadata.get("doc_type"),
                        "version": metadata.get("version"),
                    },
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def delete_by_doc_id(self, doc_id: str) -> None:
        if not self.client.collection_exists(self.collection_name):
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def search(self, query: str, top_k: int = 5):
        query_vector = self.model.encode(
            query,
            normalize_embeddings=True
        ).tolist()

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        return response.points
