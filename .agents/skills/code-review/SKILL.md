---
name: code-review
description: Use after any feature, fix, refactor, merge-conflict resolution, or documentation-impacting change in this repository to perform a production-grade review across graph-chat, auth/RBAC, memory, observability, knowledge-base lifecycle, retrieval, feedback, evaluation, tests, and documentation.
---

# Code Review

## Purpose

Provide a production-grade review that protects the repository's critical behavior and separates blocking defects from acceptable follow-up work.

## When to Use

Use this skill before handoff, before commit, after resolving conflicts, after implementing a feature, or when asked to review changes for production readiness.

## Project Context

Critical capabilities that must not regress:

- `/api/v1/graph-chat`
- JWT login and Bearer token authentication
- admin / engineer / viewer RBAC
- session_id conversation memory
- request_id observability
- JSON structured logging
- document upload / delete / reindex
- Qdrant vector search
- BM25 `chunks.json` sync
- SQL Tool safety checks
- user feedback APIs
- RAG evaluation APIs and dashboard
- Streamlit login, chat, knowledge-base management, feedback, and evaluation UI

## Key Files

- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `app/main.py`
- `app/api/routes_chat.py`
- `app/api/routes_auth.py`
- `app/api/routes_documents.py`
- `app/api/routes_feedback.py`
- `app/api/routes_evaluation.py`
- `app/core/deps.py`
- `app/core/security.py`
- `app/core/logger.py`
- `app/graph/workflow.py`
- `app/graph/state.py`
- `app/rag/graph_chain.py`
- `app/rag/hybrid_retriever.py`
- `app/rag/vectorstore.py`
- `app/rag/chunk_store.py`
- `app/services/document_service.py`
- `app/services/feedback_service.py`
- `app/services/evaluation_service.py`
- `app/tools/sql_tool.py`
- `app/graph/nodes/sql_tool_node.py`
- `scripts/init_sql_data.py`
- `scripts/test_auth_rbac.py`
- `scripts/test_document_management.py`
- `scripts/test_memory.py`
- `scripts/test_observability.py`
- `scripts/test_feedback_evaluation.py`
- `ui/streamlit_app.py`

## Required Workflow

1. Check repo status:
   - `git status --short --branch`
   - `git diff --name-status`
2. Review the actual diff before making conclusions.
3. Check whether the change violates `AGENTS.md`.
4. Check whether `/api/v1/graph-chat` request and response compatibility is preserved.
5. Check JWT/RBAC:
   - Auth-required endpoints still use `Depends`.
   - Role restrictions match route intent.
   - Viewer cannot execute SQL analysis or destructive document operations.
6. Check memory:
   - `session_id` still flows into state and response.
   - `memory_messages` remains compatible.
7. Check observability:
   - `request_id`, `metadata`, node latency, and structured logging remain intact.
8. Check knowledge-base lifecycle:
   - no full collection deletion outside legacy ingest;
   - delete/reindex are scoped by `doc_id`;
   - Qdrant and keyword/BM25 sync stay consistent.
9. Check feedback/evaluation:
   - feedback submission remains available to all roles;
   - stats/list/evaluation remain restricted to admin/engineer.
10. Check secrets and paths:
   - no hard-coded API keys, JWT secrets, tokens, or Windows-only paths.
11. Check model initialization:
   - no repeated per-request model/provider construction added to hot paths.
12. Check exception handling and audit behavior for high-risk operations.
13. Check tests and docs:
   - relevant test scripts are updated or intentionally unchanged;
   - README/docs updates are present when user-facing behavior changes.

## Constraints

- Do not rewrite unrelated code during review.
- Do not bypass RBAC to make tests pass.
- Do not hide test failures; separate code failures from environment blockers.
- Do not run destructive commands such as `git reset --hard`, full collection deletion, or database reinitialization unless explicitly authorized.
- Do not claim runtime verification when only static checks were run.

## Validation Commands

Always run when feasible:

```bash
python -m compileall app scripts
git diff --check
docker compose config --quiet
```

Run targeted tests based on changed area:

```bash
python -m scripts.test_auth_rbac
python -m scripts.test_document_management
python -m scripts.test_memory
python -m scripts.test_observability
python -m scripts.test_feedback_evaluation
python -m scripts.test_hybrid_retriever
python -m scripts.test_rule_tool
python -m scripts.test_sql_tool
python -m scripts.test_case_tool
```

Use Docker equivalents when validating container behavior:

```bash
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_feedback_evaluation
```

## Expected Output

Use exactly these sections:

- Summary
- Risk Level
- Blocking Issues
- Non-blocking Issues
- Regression Risks
- Test Results
- Required Fixes
