---
name: project-onboarding
description: Use when Codex first takes over this Industrial Quality Agentic RAG Assistant repository, performs architecture analysis, plans a large change, resolves broad uncertainty, or prepares a risk-ranked implementation plan before editing code.
---

# Project Onboarding

## Purpose

Build an accurate, repo-grounded understanding of the Industrial Quality Agentic RAG Assistant before any large implementation, refactor, merge-conflict resolution, or release preparation.

## When to Use

Use this skill when the task asks for onboarding, architecture mapping, impact analysis, a large feature plan, production-readiness review, or any change that may affect multiple subsystems.

## Project Context

This repository is an enterprise-oriented industrial quality RAG system with FastAPI, LangGraph, Qdrant, PostgreSQL, BM25, Streamlit, JWT/RBAC, request-level observability, knowledge-base management, feedback, evaluation, and audit logging.

Current request flow:

Streamlit or API client -> FastAPI -> JWT/RBAC -> LangGraph -> memory -> intent router -> Rule Tool / SQL Tool / Case Retriever / document RAG -> answer generator -> save memory -> response with request_id, citations, metadata, and latency.

## Key Files

- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/demo_script.md`
- `docs/interview_notes.md`
- `app/main.py`
- `app/api/routes_chat.py`
- `app/api/routes_auth.py`
- `app/api/routes_documents.py`
- `app/api/routes_feedback.py`
- `app/api/routes_evaluation.py`
- `app/graph/workflow.py`
- `app/graph/state.py`
- `app/rag/graph_chain.py`
- `app/rag/hybrid_retriever.py`
- `app/rag/vectorstore.py`
- `app/rag/chunk_store.py`
- `app/services/document_service.py`
- `app/core/deps.py`
- `app/core/logger.py`
- `scripts/init_sql_data.py`
- `scripts/evaluate_system.py`
- `ui/streamlit_app.py`

## Required Workflow

1. Read `AGENTS.md`, `README.md`, and the docs listed above.
2. Check the actual branch and worktree before making claims:
   - `git status --short --branch`
   - `git diff --name-status`
3. Inspect the live implementation, not only docs:
   - LangGraph workflow: `app/graph/workflow.py`
   - State and response compatibility: `app/graph/state.py`, `app/rag/graph_chain.py`, `app/schemas/chat.py`
   - Retrieval: `app/rag/hybrid_retriever.py`, `app/rag/vectorstore.py`, `app/rag/bm25_retriever.py`, `app/rag/chunk_store.py`
   - Knowledge base lifecycle: `app/services/document_service.py`, `app/api/routes_documents.py`
   - Auth/RBAC/audit: `app/core/deps.py`, `app/api/routes_auth.py`, `app/services/audit_service.py`
   - Observability: `app/core/logger.py`, `app/main.py`
   - Feedback/evaluation: `app/services/feedback_service.py`, `app/services/evaluation_service.py`
4. Output an architecture map that includes API routers, LangGraph nodes, data stores, and UI surfaces.
5. Output the main API and business links:
   - `/api/v1/auth/login`
   - `/api/v1/graph-chat`
   - `/api/v1/documents/*`
   - `/api/v1/feedback`
   - `/api/v1/evaluation/*`
6. Output data storage relationships:
   - PostgreSQL: users, audit logs, conversations, documents, chunks, feedback, evaluation, business sample tables.
   - Qdrant: vector points and payloads.
   - `data/processed/chunks.json`: BM25-compatible chunks.
   - `data/uploads`: uploaded source files.
   - `data/rules`: YAML rules.
   - `data/eval`: evaluation set and reports.
7. Identify P0/P1/P2 risks with evidence from files or commands.
8. Present an implementation plan and wait for user approval before modifying code.

## Constraints

- Do not modify code before the user approves the plan.
- Do not commit, push, reset, checkout, or delete data.
- Do not run destructive initialization or ingestion commands unless the user explicitly approves.
- Treat `scripts/init_sql_data.py` as demo-oriented database initialization.
- Treat `scripts/ingest_docs.py` as legacy demo ingestion that recreates the Qdrant collection.
- Do not claim OpenSearch, asynchronous ingestion, multi-tenancy, document ACL, OpenTelemetry, or queue workers are implemented unless current files prove it.
- Keep implemented behavior separate from roadmap or target architecture.

## Validation Commands

Use read-only or non-mutating checks by default:

```bash
git status --short --branch
git diff --name-status
rg --files app scripts docs ui data
python -m compileall app scripts
git diff --check
docker compose config --quiet
```

Run integration tests only when PostgreSQL/Qdrant and required model services are available.

## Expected Output

Return:

- Architecture map
- Main APIs and business flows
- Data storage relationship map
- P0/P1/P2 risks
- Proposed plan with files likely to change
- Validation plan split into fast checks, integration tests, and external-service/manual checks
- Explicit statement that no code was modified unless the user already approved edits
