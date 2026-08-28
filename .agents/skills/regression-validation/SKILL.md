---
name: regression-validation
description: Use when planning or running regression validation for this repository, especially before handoff, release, merge, demo, or after changes to graph-chat, retrieval, auth/RBAC, document management, observability, feedback, or evaluation.
---

# Regression Validation

## Purpose

Provide a consistent validation matrix that separates fast local checks, PostgreSQL/Qdrant integration tests, and manual checks that require real LLM or embedding services.

## When to Use

Use this skill before final handoff, before commit or PR, after conflict resolution, after feature work, after dependency/config changes, or when asked whether the project is ready to demonstrate.

## Project Context

The repository includes standalone scripts under `scripts/` rather than a single pytest suite. Some scripts are safe static checks, some require PostgreSQL/Qdrant, and some also require a real LLM or embedding/reranker model.

Do not put real paid API calls into default unit tests. LLM and external embedding validation must be opt-in or clearly labeled manual/integration.

## Key Files

- `scripts/init_sql_data.py`
- `scripts/ingest_docs.py`
- `scripts/evaluate_system.py`
- `scripts/test_auth_rbac.py`
- `scripts/test_document_management.py`
- `scripts/test_memory.py`
- `scripts/test_observability.py`
- `scripts/test_feedback_evaluation.py`
- `scripts/test_graph.py`
- `scripts/test_hybrid_retriever.py`
- `scripts/test_reranker.py`
- `scripts/test_intent.py`
- `scripts/test_rule_tool.py`
- `scripts/test_sql_tool.py`
- `scripts/test_case_tool.py`
- `scripts/test_llm.py`
- `docker-compose.yml`
- `.env.example`

## Required Workflow

1. Check branch and worktree:
   ```bash
   git status --short --branch
   git diff --name-status
   ```
2. Run fast checks first.
3. Confirm whether PostgreSQL and Qdrant are running before integration tests.
4. Confirm whether LLM and embedding credentials/cache are available before model-dependent tests.
5. Run only the validation tier appropriate to the change and user request.
6. Report each command as pass, fail, skipped, or blocked.
7. For skipped or blocked tests, state the missing dependency precisely.

## Constraints

- Do not run `scripts/ingest_docs.py` by default; it recreates the configured Qdrant collection for the legacy demo ingestion flow.
- Do not run `scripts/init_sql_data.py` against production or unknown databases; it recreates and seeds demo business tables.
- Do not run real LLM or paid embedding calls as default unit tests.
- Do not convert environment blockers into code failures.
- Do not claim Docker validation if Docker daemon access was unavailable.

## Validation Commands

### Fast checks without external services

These should not require PostgreSQL, Qdrant, LLM, or embedding APIs:

```bash
python -m compileall app scripts
git diff --check
docker compose config --quiet
python -m scripts.test_intent
python -m scripts.test_rule_tool
```

### PostgreSQL / Qdrant integration tests

Requires initialized PostgreSQL and, where noted, Qdrant plus cached or downloadable embedding models:

```bash
python -m scripts.init_sql_data
python -m scripts.test_auth_rbac
python -m scripts.test_document_management
python -m scripts.test_feedback_evaluation
python -m scripts.test_sql_tool
python -m scripts.test_case_tool
```

Retrieval-specific integration tests require Qdrant and embedding/reranker models:

```bash
python -m scripts.test_hybrid_retriever
python -m scripts.test_reranker
```

### LLM or full RAG manual/integration checks

Requires LLM credentials and usually PostgreSQL, Qdrant, chunks, and model availability:

```bash
python -m scripts.test_memory
python -m scripts.test_observability
python -m scripts.test_graph
python -m scripts.test_chain
python -m scripts.test_llm
python -m scripts.evaluate_system
```

Feedback evaluation has an optional LLM path:

```bash
RUN_EVALUATION_TEST=true python -m scripts.test_feedback_evaluation
```

PowerShell equivalent:

```powershell
$env:RUN_EVALUATION_TEST = "true"
python -m scripts.test_feedback_evaluation
Remove-Item Env:\RUN_EVALUATION_TEST
```

### Docker container checks

Requires Docker daemon access and running services:

```bash
docker compose config --quiet
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_memory
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_feedback_evaluation
```

### Legacy ingestion setup

Run only for intentional demo knowledge-base initialization:

```bash
python -m scripts.ingest_docs
```

This writes `data/processed/chunks.json` and recreates the configured Qdrant collection.

## Expected Output

Return:

- Commands run
- Pass/fail/skipped/blocked status for each command
- Environment dependencies detected
- Regression areas covered
- Regression areas not covered
- Clear next actions for any failure or blocker
