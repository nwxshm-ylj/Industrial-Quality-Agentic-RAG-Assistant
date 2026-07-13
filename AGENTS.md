# AGENTS.md

## Project Overview

This is an enterprise-oriented Industrial Quality Agentic RAG Assistant.

The system is built with:

- FastAPI
- LangGraph
- LangChain
- Qdrant
- PostgreSQL
- BM25
- Streamlit
- Docker Compose
- JWT Authentication
- RBAC
- Structured logging
- Request-level observability
- Knowledge base document management

The project targets industrial quality scenarios, including document QA, fault diagnosis, rule lookup, SQL analysis, and historical case retrieval.

## Core Architecture

Main request flow:

User / Streamlit
→ FastAPI
→ Auth / RBAC
→ LangGraph Workflow
→ Intent Router
→ RAG / Rule Tool / SQL Tool / Case Retriever
→ Answer Generator
→ Save Memory
→ Response with request_id, citations, and metadata

## Critical Existing Capabilities

Do not break these capabilities:

1. `/api/v1/graph-chat`
2. JWT login and Bearer token authentication
3. admin / engineer / viewer RBAC
4. session_id conversation memory
5. request_id observability
6. JSON structured logging
7. document upload / delete / reindex
8. Qdrant vector search
9. BM25 chunks.json sync
10. SQL Tool safety checks
11. Streamlit login and knowledge base management

## Important Commands

Run database initialization:

```bash
python -m scripts.init_sql_data