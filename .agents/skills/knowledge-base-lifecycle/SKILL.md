---
name: knowledge-base-lifecycle
description: Use when changing document upload, parsing, chunking, PostgreSQL document metadata, Qdrant indexing, BM25/chunks.json synchronization, keyword index synchronization, document deletion, or document reindex behavior.
---

# Knowledge Base Lifecycle

## Purpose

Keep document metadata, chunks, vector index, keyword index, status transitions, and audit/log behavior consistent across upload, delete, and reindex operations.

## When to Use

Use this skill for document parsing, upload APIs, duplicate detection, document versioning, chunk creation, PostgreSQL writes, Qdrant writes/deletes, `chunks.json` refresh, future keyword-index integration, deletion, or reindexing.

## Project Context

Current enterprise knowledge-base implementation:

- API: `app/api/routes_documents.py`
- Service: `app/services/document_service.py`
- Schemas: `app/schemas/document.py`
- Parser: `app/rag/loader.py`
- Splitter: `app/rag/splitter.py`
- Vector store: `app/rag/vectorstore.py`
- BM25 sync: `app/rag/chunk_store.py`
- Database tables: `documents`, `document_chunks`
- Legacy demo ingestion: `scripts/ingest_docs.py`

Current keyword path is file-backed BM25 using `data/processed/chunks.json`. OpenSearch is a target architecture option, not implemented in the current repo.

## Key Files

- `app/api/routes_documents.py`
- `app/services/document_service.py`
- `app/schemas/document.py`
- `app/rag/loader.py`
- `app/rag/splitter.py`
- `app/rag/vectorstore.py`
- `app/rag/chunk_store.py`
- `app/rag/bm25_retriever.py`
- `scripts/init_sql_data.py`
- `scripts/ingest_docs.py`
- `scripts/test_document_management.py`
- `data/uploads`
- `data/processed/chunks.json`

## Required Workflow

### Upload

Follow this lifecycle:

```text
upload
-> validate file
-> sanitize filename
-> compute content_hash
-> create documents row with uploaded status
-> save file under data/uploads
-> parse
-> chunk
-> write document_chunks in PostgreSQL
-> write Qdrant points with doc_id and chunk_id payloads
-> refresh keyword index or chunks.json
-> mark documents.status = indexed
```

### Delete

Delete only by `doc_id`:

1. Load document metadata.
2. Delete Qdrant points using payload filter `doc_id`.
3. Delete keyword index entries by `doc_id` or refresh `chunks.json` from PostgreSQL.
4. Delete `document_chunks` rows for that `doc_id`.
5. Mark `documents.status = deleted` and update `chunk_count`.
6. Do not delete other documents, legacy chunks, or the full Qdrant collection.

### Reindex

Reindex only the selected document:

1. Load `documents.file_path`.
2. Mark the document as an in-progress non-indexed state.
3. Delete old Qdrant and keyword entries for the selected `doc_id`.
4. Reparse and split the stored source file.
5. Replace `document_chunks` for that `doc_id`.
6. Write new Qdrant points and keyword entries.
7. Mark `documents.status = indexed` only after both retrieval indexes are successfully updated.
8. Mark `documents.status = failed` and emit structured logs if a partial failure occurs.

## Constraints

- Do not delete the full Qdrant collection during enterprise upload, delete, or reindex.
- Do not break the legacy `data/raw_docs` and `scripts/ingest_docs.py` demo flow.
- Do not write Windows-specific absolute paths.
- Use `pathlib` for path handling.
- Preserve `doc_id`, `chunk_id`, `source`, `doc_type`, and `version` payloads.
- Do not mark a document `indexed` before PostgreSQL chunks, Qdrant vectors, and keyword/chunks synchronization have succeeded.
- Partial failures must set `documents.status = failed` when a document record exists.
- Emit structured logs for lifecycle events and errors.
- Enforce RBAC through `app/core/deps.py`; front-end role hiding is not a security boundary.

## Validation Commands

Fast checks:

```bash
python -m compileall app scripts
git diff --check
```

Database and Qdrant integration checks:

```bash
python -m scripts.init_sql_data
python -m scripts.test_document_management
```

Docker validation:

```bash
docker compose config --quiet
docker compose exec api python -m scripts.test_document_management
```

If changing upload UI behavior, also manually test Streamlit Knowledge Base Management with admin and engineer roles.

## Expected Output

Return:

- Lifecycle stage summary for upload/delete/reindex
- Files and tables affected
- Index consistency analysis
- Failure-mode behavior
- RBAC impact
- Validation results and any environment blockers
