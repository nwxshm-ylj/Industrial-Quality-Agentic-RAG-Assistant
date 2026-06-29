from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class QdrantVectorStore:
    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url)
        self.model = SentenceTransformer(settings.embedding_model)
        self.collection_name = settings.qdrant_collection

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