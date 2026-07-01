# Deployment Guide

## 1. Prerequisites

Recommended local environment:

- Docker Desktop or Docker Engine with Compose v2
- 8 GB RAM minimum; more if Reranker is enabled
- Internet access for the configured LLM and first embedding-model download
- Available ports 8000, 30000, 5432, 6333, and 6334

The repository mounts the local data directory into API, Streamlit, and tool containers. Ensure it is writable.

## 2. Environment variables

Copy the template:

~~~bash
cp .env.example .env
~~~

PowerShell:

~~~powershell
Copy-Item .env.example .env
~~~

| Variable | Example/default | Purpose |
|---|---|---|
| LLM_MODEL | qwen-plus | OpenAI-compatible chat model |
| LLM_API_KEY | required | Model provider credential |
| LLM_BASE_URL | DashScope-compatible endpoint | Model API base URL |
| QDRANT_URL | http://localhost:6333 | Host-side Qdrant URL |
| QDRANT_COLLECTION | industrial_docs | Vector collection |
| EMBEDDING_MODEL | BAAI/bge-small-zh-v1.5 | Embedding model |
| DATABASE_URL | PostgreSQL SQLAlchemy URL | Host-side database connection |
| RERANKER_MODEL | BAAI/bge-reranker-base | Optional reranker |
| USE_RERANKER | false | Enable CrossEncoder reranking |
| JWT_SECRET_KEY | change_me | JWT signing secret |
| JWT_ALGORITHM | HS256 | JWT algorithm |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 1440 | Token lifetime |
| LOG_LEVEL | INFO | Application log level |
| RAG_API_URL | local graph-chat URL | Streamlit API target outside Compose |

Do not commit a real .env file. Production secrets should come from a secrets manager or orchestrator secret.

## 3. Docker Compose deployment

### 3.1 Start stateful services

~~~bash
docker compose up -d qdrant postgres
docker compose ps
~~~

Wait until PostgreSQL accepts connections. If the initialization command runs too early, retry it after several seconds.

### 3.2 Initialize PostgreSQL

~~~bash
docker compose --profile tools run --rm init-sql
~~~

This command:

- recreates and seeds inspection_record, equipment_alarm, and quality_cases;
- idempotently creates memory, document, user, audit, feedback, and evaluation tables;
- creates admin/admin123 only when admin does not already exist.

Warning: it is a demo initialization command and must not target a production database containing real business records.

### 3.3 Initialize the legacy demo knowledge base

~~~bash
docker compose --profile tools run --rm ingest
~~~

The script loads Markdown files from data/raw_docs, writes data/processed/chunks.json, and recreates the configured Qdrant collection. Use it for initial demo setup, not enterprise incremental updates.

### 3.4 Start API and Streamlit

~~~bash
docker compose up -d --build api streamlit
~~~

Endpoints:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Streamlit: http://localhost:30000
- Qdrant: http://localhost:6333/dashboard

### 3.5 Verify

~~~bash
curl http://localhost:8000/health
docker compose logs --tail=100 api
~~~

Expected health response:

~~~json
{"status":"ok"}
~~~

## 4. Local application development

Run PostgreSQL and Qdrant with Docker while running Python locally:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

docker compose up -d postgres qdrant
python -m scripts.init_sql_data
python -m scripts.ingest_docs
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
~~~

PowerShell activation:

~~~powershell
.\.venv\Scripts\Activate.ps1
~~~

Start Streamlit in another terminal:

~~~bash
streamlit run ui/streamlit_app.py
~~~

## 5. Data persistence and backup

Docker volumes:

- postgres_data: relational and audit data.
- qdrant_data: vector collection.
- hf_cache: downloaded embedding/reranker models.

Bind-mounted path:

- ./data:/app/data

Before upgrading:

1. Back up PostgreSQL with pg_dump.
2. Snapshot or back up Qdrant storage.
3. Back up data/uploads, data/processed, data/rules, and data/eval.
4. Record image tags and environment variables.
5. Test restore procedures in a non-production environment.

Do not use docker compose down -v unless deleting all local state is intentional.

## 6. Common troubleshooting

### PostgreSQL connection refused

Symptoms: psycopg2 OperationalError or connection refused.

~~~bash
docker compose ps postgres
docker compose logs postgres
docker compose restart postgres
~~~

Check that local DATABASE_URL uses localhost, while containers use hostname postgres.

### Qdrant unavailable

~~~bash
curl http://localhost:6333/collections
docker compose logs qdrant
~~~

Inside Compose the API uses http://qdrant:6333, not localhost.

### Embedding model cannot download

- Confirm Hugging Face network access.
- Check disk space in hf_cache.
- Retry after the first download completes.
- For restricted networks, pre-populate the cache or use an approved internal model registry.
- Do not enable offline mode until all required model artifacts are cached.

### LLM authentication or connection error

- Verify LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL.
- Confirm the endpoint supports the OpenAI chat-completions protocol.
- Test connectivity from inside the API container.
- Check provider quotas, TLS interception, and proxy configuration.

### 401 Unauthorized

- Login again and use Authorization: Bearer TOKEN.
- Confirm the user is active.
- Confirm API replicas use the same JWT_SECRET_KEY.
- Check token expiration and system clock.

### 403 Forbidden

The token is valid but the role lacks permission. Check the RBAC matrix. Viewer cannot execute SQL analysis, upload/delete/reindex documents, view global feedback, or run evaluation.

### Uploaded document is not found by BM25

Document operations update chunks.json, but the current API process has an in-memory BM25 index. Restart API:

~~~bash
docker compose restart api
~~~

Qdrant vector retrieval sees newly indexed vectors immediately.

### Upload directory or chunks.json is read-only

Ensure the host data directory is writable by Docker. On Linux check ownership and mount options. Do not mount data as read-only.

### Port conflict

Change the host side of the relevant docker-compose port mapping or stop the conflicting local service.

## 7. Production security checklist

- Replace admin/admin123 immediately.
- Use a long random JWT_SECRET_KEY and rotate it under an explicit policy.
- Store secrets outside source control.
- Terminate TLS at a trusted reverse proxy or ingress.
- Restrict PostgreSQL and Qdrant to private networks.
- Use a dedicated read-only PostgreSQL user for SQL Tool queries.
- Configure statement timeout, connection limits, and database resource quotas.
- Add rate limiting, request-size limits, upload quotas, and malware scanning.
- Validate MIME type in addition to extension for untrusted uploads.
- Define audit-log access, retention, masking, and export policies.
- Do not return sensitive contexts or SQL rows to unauthorized users.
- Pin images and dependencies; add SBOM, SAST, dependency, and image scanning.
- Back up PostgreSQL, Qdrant, and source documents and test restoration.
- Run evaluation before promoting model, prompt, embedding, or index changes.

## 8. Release verification

~~~bash
python -m compileall app scripts
git diff --check

docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_memory
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_feedback_evaluation
~~~

A complete verification requires PostgreSQL, Qdrant, cached/downloadable embeddings, and a working LLM endpoint.
