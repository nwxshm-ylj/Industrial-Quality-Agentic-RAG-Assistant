---
name: online-hybrid-search
description: Use when modifying or designing retrieval for this project, including Qwen or other EmbeddingProvider changes, Qdrant vector search, target OpenSearch keyword search, RRF or weighted fusion, chunks.json runtime dependency, retrieval citations, or graph-chat response compatibility.
---

# Online Hybrid Search

## Purpose

Protect retrieval quality, cost, index consistency, and response compatibility when changing the project's hybrid search path.

## When to Use

Use this skill for changes to embedding providers, vector dimensions, Qdrant collection usage, BM25 or future OpenSearch keyword retrieval, fusion strategy, citations, `contexts`, `chunks.json`, reranking, or retrieval tests.

## Project Context

Current implementation:

- Vector search: `app/rag/vectorstore.py` uses `SentenceTransformer(settings.embedding_model)` and Qdrant.
- Keyword search: `app/rag/bm25_retriever.py` loads `data/processed/chunks.json`.
- Fusion: `app/rag/hybrid_retriever.py` uses weighted score fusion with defaults `vector_weight=0.65` and `bm25_weight=0.35`.
- Optional reranking: `app/rag/reranker.py`.
- LangGraph retrieval node: `app/graph/nodes/retrieve_node.py`.
- API response compatibility: `app/schemas/chat.py` and `app/rag/graph_chain.py`.

Target architecture only, not currently implemented:

- Qwen/DashScope EmbeddingProvider abstraction.
- OpenSearch or Elasticsearch-backed online keyword retrieval.
- RRF-based fusion or configurable weighted fusion across online vector and keyword indexes.
- Hybrid search that does not depend on runtime `chunks.json`.

## Key Files

- `app/core/config.py`
- `app/rag/vectorstore.py`
- `app/rag/hybrid_retriever.py`
- `app/rag/bm25_retriever.py`
- `app/rag/chunk_store.py`
- `app/rag/reranker.py`
- `app/graph/nodes/retrieve_node.py`
- `app/rag/graph_chain.py`
- `app/schemas/chat.py`
- `app/services/document_service.py`
- `scripts/ingest_docs.py`
- `scripts/test_hybrid_retriever.py`
- `scripts/test_reranker.py`
- `scripts/test_graph.py`

## Required Workflow

1. Confirm whether the task targets current implementation or target architecture.
2. Inspect current settings and collection usage before editing:
   - `app/core/config.py`
   - `.env.example`
   - `app/rag/vectorstore.py`
3. Identify all index writers and readers:
   - Legacy writer: `scripts/ingest_docs.py`
   - Enterprise writer: `app/services/document_service.py`
   - Vector reader: `QdrantVectorStore.search`
   - Keyword reader: `BM25Retriever`
4. Preserve `graph-chat` response fields:
   - `answer`
   - `citations`
   - `request_id`
   - `session_id`
   - `memory_messages`
   - `metadata`
   - `intent`
   - `rewritten_query`
   - `evidence_score`
   - `evidence_enough`
   - `retry_count`
   - `contexts`
5. If introducing an EmbeddingProvider abstraction, define separate methods for document embedding and query embedding.
6. If changing vector dimensions, create or migrate to a separate Qdrant collection; do not mix old and new dimensions in one collection.
7. If introducing OpenSearch, implement it as target architecture and keep old BM25 behavior compatible until migration is complete.
8. Add tests with mock embeddings for unit-level behavior and reserve real provider calls for opt-in integration/manual validation.

## Constraints

- Do not create an EmbeddingProvider or SentenceTransformer model inside every request path.
- Do not download Hugging Face models during runtime in production paths.
- API keys must be read from environment/settings only; never hard-code credentials.
- Document embedding and query embedding must be separate calls or methods.
- Do not mix old and new vector dimensions in the same Qdrant collection.
- Do not delete the full Qdrant collection for incremental retrieval changes.
- Do not run `scripts/ingest_docs.py` unless the user accepts that it recreates the configured Qdrant collection.
- Hybrid Search queries must not depend on `chunks.json` in the target online architecture.
- Preserve current `chunks.json` compatibility while the project still uses file-backed BM25.
- Preserve `graph-chat` response compatibility.
- Unit tests must use mock embeddings and must not call real paid APIs by default.

## Validation Commands

Fast checks:

```bash
python -m compileall app scripts
git diff --check
```

Current integration checks, requiring Qdrant and available/cached embedding models:

```bash
python -m scripts.test_hybrid_retriever
python -m scripts.test_reranker
```

End-to-end checks, requiring PostgreSQL/Qdrant and usually LLM access:

```bash
python -m scripts.test_graph
python -m scripts.test_observability
python -m scripts.test_memory
```

For new unit tests around fusion or provider selection, use mocks instead of real Qwen, OpenAI, DashScope, Hugging Face, or paid embedding APIs.

## Expected Output

Return:

- Current vs target architecture distinction
- Index writers/readers affected
- Vector dimension and collection migration decision
- Fusion strategy and citation behavior
- Compatibility impact on `/api/v1/graph-chat`
- Test plan with mock/unit, integration, and manual external API checks separated
