"""Backfill Neo4j document traceability data from PostgreSQL.

This command does not parse files, call embedding APIs, or rebuild Qdrant and
OpenSearch. It reuses the indexed documents and chunks already persisted in
PostgreSQL, enriches missing deterministic quality entities in memory, and
idempotently synchronizes each document into Neo4j.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.knowledge_graph.service import get_knowledge_graph_service
from app.traceability.entity_linker import QualityEntityLinker
from app.traceability.taxonomy import normalize_document_type


def load_indexed_documents(doc_id: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE d.status = 'indexed'"
    params: dict[str, Any] = {}
    if doc_id:
        where += " AND d.doc_id = :doc_id"
        params["doc_id"] = doc_id

    query = text(
        f"""
        SELECT
            d.doc_id,
            d.filename,
            d.doc_type AS document_doc_type,
            d.version AS document_version,
            c.chunk_id,
            c.chunk_index,
            c.text,
            c.doc_type AS chunk_doc_type,
            c.source,
            c.version AS chunk_version,
            c.metadata
        FROM documents d
        JOIN document_chunks c ON c.doc_id = d.doc_id
        {where}
        ORDER BY d.doc_id, c.chunk_index
        """
    )
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(query, params).mappings()]


def build_graph_payloads(rows: list[dict[str, Any]]) -> list[tuple[dict, list[dict]]]:
    linker = QualityEntityLinker()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["doc_id"])].append(row)

    payloads: list[tuple[dict, list[dict]]] = []
    for doc_id, document_rows in grouped.items():
        first = document_rows[0]
        document_type = normalize_document_type(
            first.get("document_doc_type"),
            filename=str(first.get("filename") or ""),
        )
        document = {
            "doc_id": doc_id,
            "filename": first.get("filename"),
            "doc_type": document_type,
            "version": first.get("document_version") or "v1",
        }
        chunks: list[dict] = []
        for row in document_rows:
            metadata = dict(row.get("metadata") or {})
            source = row.get("source") or first.get("filename")
            chunk_type = normalize_document_type(
                row.get("chunk_doc_type") or document_type,
                filename=str(source or ""),
            )
            quality_entities = metadata.get("quality_entities")
            if not quality_entities:
                quality_entities = linker.link(f"{source}\n{row.get('text') or ''}")
            metadata.update(
                {
                    "doc_id": doc_id,
                    "chunk_id": row["chunk_id"],
                    "chunk_index": row["chunk_index"],
                    "source": source,
                    "doc_type": chunk_type,
                    "version": row.get("chunk_version") or document["version"],
                    "quality_entities": quality_entities,
                }
            )
            chunks.append({"text": row.get("text") or "", "metadata": metadata})
        payloads.append((document, chunks))
    return payloads


def backfill_document_graph(doc_id: str | None = None) -> dict[str, int]:
    if not settings.knowledge_graph_enabled:
        raise RuntimeError("KNOWLEDGE_GRAPH_ENABLED must be true before graph backfill")

    payloads = build_graph_payloads(load_indexed_documents(doc_id))
    if doc_id and not payloads:
        raise ValueError(f"indexed document not found: {doc_id}")

    service = get_knowledge_graph_service()
    document_count = 0
    chunk_count = 0
    failures: list[tuple[str, str]] = []
    for document, chunks in payloads:
        try:
            service.sync_document(document, chunks)
            document_count += 1
            chunk_count += len(chunks)
            print(
                {
                    "status": "synced",
                    "doc_id": document["doc_id"],
                    "doc_type": document["doc_type"],
                    "chunk_count": len(chunks),
                }
            )
        except Exception as exc:
            failures.append((document["doc_id"], str(exc)))
            print({"status": "failed", "doc_id": document["doc_id"], "error": str(exc)})

    if failures:
        raise RuntimeError(
            f"Neo4j document backfill failed for {len(failures)} document(s): {failures}"
        )
    return {"documents": document_count, "chunks": chunk_count}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc-id", help="Only backfill one indexed document")
    args = parser.parse_args()
    result = backfill_document_graph(args.doc_id)
    print({"status": "success", **result})


if __name__ == "__main__":
    main()
