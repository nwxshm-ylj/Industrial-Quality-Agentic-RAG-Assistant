from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.knowledge_graph.base import KnowledgeGraphError
from app.traceability.entity_linker import QualityEntityLinker


class Neo4jKnowledgeGraphBackend:
    def __init__(self, driver: Any, *, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT document_doc_id IF NOT EXISTS "
            "FOR (n:Document) REQUIRE n.doc_id IS UNIQUE",
            "CREATE CONSTRAINT document_chunk_id IF NOT EXISTS "
            "FOR (n:DocumentChunk) REQUIRE n.chunk_id IS UNIQUE",
            "CREATE CONSTRAINT quality_entity_key IF NOT EXISTS "
            "FOR (n:QualityEntity) REQUIRE n.entity_key IS UNIQUE",
        ]
        try:
            with self.driver.session(database=self.database) as session:
                for statement in statements:
                    session.run(statement).consume()
        except Exception as exc:
            raise KnowledgeGraphError(f"Neo4j schema setup failed: {exc}") from exc

    def upsert_document_chunks(
        self,
        document: dict,
        chunks: list[dict],
    ) -> None:
        doc_id = str(document.get("doc_id") or "").strip()
        if not doc_id:
            raise ValueError("document doc_id is required for graph sync")

        def write_graph(tx):
            tx.run(
                """
                MERGE (d:Document {doc_id: $doc_id})
                SET d.name = $filename,
                    d.doc_type = $doc_type,
                    d.version = $version,
                    d.status = 'indexed'
                """,
                doc_id=doc_id,
                filename=document.get("filename"),
                doc_type=document.get("doc_type"),
                version=document.get("version"),
            ).consume()
            tx.run(
                """
                MATCH (d:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(old:DocumentChunk)
                DETACH DELETE old
                """,
                doc_id=doc_id,
            ).consume()

            for chunk in chunks:
                metadata = chunk.get("metadata", {})
                chunk_id = str(metadata.get("chunk_id") or "").strip()
                if not chunk_id:
                    raise ValueError("chunk_id is required for graph sync")
                tx.run(
                    """
                    MATCH (d:Document {doc_id: $doc_id})
                    MERGE (c:DocumentChunk {chunk_id: $chunk_id})
                    SET c.name = $chunk_id,
                        c.doc_id = $doc_id,
                        c.source = $source,
                        c.doc_type = $doc_type,
                        c.version = $version,
                        c.page_start = $page_start,
                        c.page_end = $page_end,
                        c.heading_path = $heading_path,
                        c.text_preview = $text_preview
                    MERGE (d)-[:HAS_CHUNK]->(c)
                    """,
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    source=metadata.get("source"),
                    doc_type=metadata.get("doc_type"),
                    version=metadata.get("version"),
                    page_start=metadata.get("page_start"),
                    page_end=metadata.get("page_end"),
                    heading_path=metadata.get("heading_path"),
                    text_preview=str(chunk.get("text", ""))[:1000],
                ).consume()
                quality_entities = metadata.get("quality_entities") or {}
                for entity in QualityEntityLinker.graph_entities(quality_entities):
                    entity_key = f"{entity['entity_type']}:{entity['canonical_key']}"
                    tx.run(
                        """
                        MATCH (c:DocumentChunk {chunk_id: $chunk_id})
                        MERGE (e:QualityEntity {entity_key: $entity_key})
                        SET e.name = $name,
                            e.canonical_key = $canonical_key,
                            e.entity_type = $entity_type,
                            e.label_name = $label_name
                        MERGE (c)-[r:MENTIONS]->(e)
                        SET r.doc_id = $doc_id,
                            r.source = $source,
                            r.page_start = $page_start,
                            r.page_end = $page_end
                        """,
                        chunk_id=chunk_id,
                        entity_key=entity_key,
                        name=entity["name"],
                        canonical_key=entity["canonical_key"],
                        entity_type=entity["entity_type"],
                        label_name=entity["label"],
                        doc_id=doc_id,
                        source=metadata.get("source"),
                        page_start=metadata.get("page_start"),
                        page_end=metadata.get("page_end"),
                    ).consume()
            tx.run(
                "MATCH (e:QualityEntity) WHERE NOT (e)--() DELETE e"
            ).consume()

        try:
            with self.driver.session(database=self.database) as session:
                session.execute_write(write_graph)
        except Exception as exc:
            if isinstance(exc, (ValueError, KnowledgeGraphError)):
                raise
            raise KnowledgeGraphError(
                f"Neo4j document graph upsert failed: {exc}"
            ) from exc

    def delete_document(self, doc_id: str) -> None:
        try:
            with self.driver.session(database=self.database) as session:
                session.run(
                    """
                    MATCH (:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(c:DocumentChunk)
                    DETACH DELETE c
                    """,
                    doc_id=doc_id,
                ).consume()
                session.run(
                    "MATCH (d:Document {doc_id: $doc_id}) DETACH DELETE d",
                    doc_id=doc_id,
                ).consume()
                session.run(
                    "MATCH (e:QualityEntity) WHERE NOT (e)--() DELETE e"
                ).consume()
        except Exception as exc:
            raise KnowledgeGraphError(
                f"Neo4j document graph delete failed: {exc}"
            ) from exc

    def search_traceability(
        self,
        entity_keys: list[str],
        limit: int,
    ) -> list[dict]:
        if not entity_keys or limit <= 0:
            return []
        query = """
        MATCH (anchor:QualityEntity)<-[:MENTIONS]-(chunk:DocumentChunk)
              <-[:HAS_CHUNK]-(document:Document)
        WHERE any(value IN $entity_keys
                  WHERE anchor.canonical_key = value
                     OR toLower(anchor.name) CONTAINS value)
        OPTIONAL MATCH (chunk)-[:MENTIONS]->(related:QualityEntity)
        WITH anchor, chunk, document,
             collect(DISTINCT {
                labels: ['QualityEntity'],
                name: related.name,
                canonical_key: related.canonical_key,
                entity_type: related.entity_type
             }) AS related_entities
        RETURN
          [
            {
              labels: ['QualityEntity'], name: anchor.name,
              canonical_key: anchor.canonical_key,
              entity_type: anchor.entity_type
            },
            {
              labels: ['DocumentChunk'], name: chunk.chunk_id,
              chunk_id: chunk.chunk_id, source: chunk.source,
              page_start: chunk.page_start, page_end: chunk.page_end
            },
            {
              labels: ['Document'], name: document.name,
              doc_id: document.doc_id, doc_type: document.doc_type,
              version: document.version
            }
          ] + related_entities AS nodes,
          ['MENTIONS', 'HAS_CHUNK'] AS relationships
        LIMIT $limit
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    query,
                    entity_keys=[value.lower() for value in entity_keys],
                    limit=limit,
                )
                return [dict(record) for record in result]
        except Exception as exc:
            raise KnowledgeGraphError(
                f"Neo4j traceability search failed: {exc}"
            ) from exc

    def close(self) -> None:
        self.driver.close()


@lru_cache(maxsize=1)
def get_neo4j_backend() -> Neo4jKnowledgeGraphBackend:
    from neo4j import GraphDatabase

    from app.core.config import settings

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
        connection_timeout=settings.neo4j_connection_timeout_seconds,
        max_connection_pool_size=settings.neo4j_max_connection_pool_size,
    )
    return Neo4jKnowledgeGraphBackend(
        driver,
        database=settings.neo4j_database,
    )
