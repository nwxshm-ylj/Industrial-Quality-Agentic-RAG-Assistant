from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from uuid import uuid4

from sqlalchemy import text

from app.core.config import settings
from app.core.logger import log_business_event
from app.db.session import engine
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.index_activation import activate_validated_vector_alias
from app.rag.loader import load_markdown_docs
from app.rag.search_backends.opensearch_backend import OpenSearchKeywordBackend
from app.rag.search_backends.qdrant_backend import QdrantVectorSearchBackend
from app.rag.splitter import infer_doc_type, split_docs


def _build_backends():
    provider = get_embedding_provider()
    vector_backend = QdrantVectorSearchBackend(
        provider,
        collection_name=settings.qdrant_collection,
        collection_alias=settings.qdrant_collection_alias,
    )
    keyword_backend = OpenSearchKeywordBackend(
        index_name=(
            f"{settings.opensearch_index_prefix}_keyword_"
            f"{settings.keyword_index_version}"
        )
    )
    return vector_backend, keyword_backend


def migrate_online_indexes() -> dict:
    """Build both indexes without changing the active Qdrant alias."""

    vector_backend, keyword_backend = _build_backends()
    vector_backend.ensure_index()
    keyword_backend.ensure_index()
    if vector_backend.get_alias_target() == settings.qdrant_collection:
        raise RuntimeError(
            "The active alias already targets the online collection; "
            "use per-document reindex instead of full migration"
        )

    documents = _load_legacy_documents() + _load_managed_documents()
    indexed_chunks = 0
    migration_id = uuid4().hex

    for document in documents:
        doc_id = document["doc_id"]
        operation_id = migration_id
        chunks = _copy_chunks(document["chunks"])
        promoted = False
        try:
            vector_backend.upsert_document_chunks(
                doc_id,
                chunks,
                index_status="staging",
                index_operation_id=operation_id,
            )
            keyword_backend.upsert_document_chunks(
                doc_id,
                chunks,
                index_status="staging",
                index_operation_id=operation_id,
            )
            vector_backend.set_document_index_status(
                doc_id,
                "indexed",
                index_operation_id=operation_id,
            )
            keyword_backend.set_document_index_status(
                doc_id,
                "indexed",
                index_operation_id=operation_id,
            )
            promoted = True
            vector_backend.delete_by_doc_id(
                doc_id,
                exclude_operation_id=operation_id,
            )
            keyword_backend.delete_by_doc_id(
                doc_id,
                exclude_operation_id=operation_id,
            )
            indexed_chunks += len(chunks)
        except Exception as exc:
            if not promoted:
                _cleanup_operation(
                    vector_backend,
                    keyword_backend,
                    doc_id,
                    operation_id,
                )
            log_business_event(
                "online_index_migration_failed",
                status="failed",
                error_message=str(exc),
                doc_id=doc_id,
                qdrant_collection=settings.qdrant_collection,
                qdrant_collection_alias=settings.qdrant_collection_alias,
            )
            raise RuntimeError(
                f"Online index migration failed for {doc_id}; alias unchanged"
            ) from exc

    try:
        vector_backend.delete_all_except_operation(migration_id)
        keyword_backend.delete_all_except_operation(migration_id)
        vector_count = vector_backend.count_indexed()
        keyword_count = keyword_backend.count_indexed()
        if vector_count != indexed_chunks or keyword_count != indexed_chunks:
            raise RuntimeError(
                "Online index counts do not match the migration manifest: "
                f"expected={indexed_chunks}, qdrant={vector_count}, "
                f"opensearch={keyword_count}"
            )
    except Exception as exc:
        log_business_event(
            "online_index_migration_failed",
            status="failed",
            error_message=str(exc),
            migration_id=migration_id,
            failed_stage="migration_validation",
            qdrant_collection=settings.qdrant_collection,
            qdrant_collection_alias=settings.qdrant_collection_alias,
        )
        raise RuntimeError(
            "Online index migration validation failed; alias unchanged"
        ) from exc

    result = {
        "documents": len(documents),
        "chunks": indexed_chunks,
        "qdrant_collection": settings.qdrant_collection,
        "qdrant_collection_alias": settings.qdrant_collection_alias,
        "opensearch_index": keyword_backend.index_name,
        "alias_activated": False,
        "migration_id": migration_id,
    }
    log_business_event("online_index_migration_completed", **result)
    return result


def activate_online_alias() -> dict:
    """Activate an already migrated and externally tested index pair."""

    vector_backend, keyword_backend = _build_backends()
    vector_backend.ensure_index()
    keyword_backend.ensure_index()
    result = activate_validated_vector_alias(
        vector_backend,
        keyword_backend,
    )
    result.update(
        {
            "qdrant_collection": settings.qdrant_collection,
            "qdrant_collection_alias": settings.qdrant_collection_alias,
            "opensearch_index": keyword_backend.index_name,
        }
    )
    log_business_event("online_index_alias_activated", **result)
    return result


def _load_legacy_documents() -> list[dict]:
    raw_docs = load_markdown_docs("data/raw_docs")
    documents = []
    for document in raw_docs:
        source = document["source"]
        doc_id = "legacy_" + hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest()[:24]
        chunks = split_docs([document])
        for index, chunk in enumerate(chunks):
            chunk["metadata"].update(
                {
                    "doc_id": doc_id,
                    "chunk_id": f"{doc_id}_{index}",
                    "chunk_index": index,
                    "source": source,
                    "doc_type": infer_doc_type(source),
                    "version": "legacy-v1",
                }
            )
        documents.append({"doc_id": doc_id, "chunks": chunks})
    return documents


def _load_managed_documents() -> list[dict]:
    query = text("""
        SELECT
            dc.doc_id, dc.chunk_id, dc.chunk_index, dc.text,
            dc.doc_type, dc.source, dc.version
        FROM document_chunks AS dc
        JOIN documents AS d ON d.doc_id = dc.doc_id
        WHERE d.status = 'indexed'
        ORDER BY dc.doc_id, dc.chunk_index
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["doc_id"]].append(
            {
                "text": row["text"],
                "metadata": {
                    "doc_id": row["doc_id"],
                    "chunk_id": row["chunk_id"],
                    "chunk_index": row["chunk_index"],
                    "doc_type": row["doc_type"],
                    "source": row["source"],
                    "version": row["version"],
                },
            }
        )
    return [
        {"doc_id": doc_id, "chunks": chunks}
        for doc_id, chunks in grouped.items()
    ]


def _copy_chunks(chunks: list[dict]) -> list[dict]:
    copied = []
    for chunk in chunks:
        metadata = dict(chunk.get("metadata", {}))
        copied.append({"text": chunk["text"], "metadata": metadata})
    return copied


def _cleanup_operation(
    vector_backend,
    keyword_backend,
    doc_id: str,
    operation_id: str,
) -> None:
    for backend in (vector_backend, keyword_backend):
        try:
            backend.delete_by_doc_id(
                doc_id,
                index_operation_id=operation_id,
            )
        except Exception as exc:
            log_business_event(
                "online_index_migration_compensation_failed",
                status="failed",
                error_message=str(exc),
                doc_id=doc_id,
                operation_id=operation_id,
                backend=backend.__class__.__name__,
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy and managed content to online hybrid indexes"
    )
    parser.add_argument(
        "--activate-alias",
        action="store_true",
        help=(
            "Atomically point industrial_docs_active at the new collection only "
            "after the full dual-index migration succeeds"
        ),
    )
    args = parser.parse_args()
    result = (
        activate_online_alias()
        if args.activate_alias
        else migrate_online_indexes()
    )
    print(result)


if __name__ == "__main__":
    main()
