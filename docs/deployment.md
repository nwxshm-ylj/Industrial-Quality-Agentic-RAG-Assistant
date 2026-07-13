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
| QDRANT_COLLECTION | industrial_docs_qwen_1024_v1 | Versioned online vector collection |
| QDRANT_COLLECTION_ALIAS | industrial_docs_active | Stable runtime query alias |
| LEGACY_QDRANT_COLLECTION | industrial_docs | Legacy BGE demo collection |
| QWEN_EMBEDDING_API_KEY | required for online indexing/search | DashScope embedding credential |
| QWEN_EMBEDDING_MODEL | text-embedding-v4 | Online embedding model |
| QWEN_EMBEDDING_DIMENSION | 1024 | Online vector dimension |
| OPENSEARCH_URL | http://localhost:9200 | OpenSearch endpoint |
| OPENSEARCH_INDEX_PREFIX | industrial_docs | Keyword index prefix |
| HYBRID_DEGRADED_MODE | vector_only | Keyword backend failure behavior |
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
docker compose up -d qdrant postgres opensearch
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

### 3.3 Build and validate online indexes

~~~bash
docker compose run --rm api python -m scripts.migrate_online_indexes
docker compose run --rm api python -m scripts.test_qdrant_vector_backend
docker compose run --rm api python -m scripts.test_opensearch_keyword_backend
docker compose run --rm api python -m scripts.test_online_hybrid_retriever
docker compose run --rm api python -m scripts.test_index_activation_guard
~~~

The first command builds the versioned Qdrant collection and OpenSearch keyword index without changing the stable alias. After integration and evaluation checks pass, activate the already-built index pair:

~~~bash
docker compose run --rm api python -m scripts.migrate_online_indexes --activate-alias
~~~

Alias activation is blocked when the two indexed chunk counts differ or are empty. Once the alias targets the online collection, use the Document API reindex operation for repairs instead of running the full migration again.

Legacy Demo ingestion remains available as an explicit, destructive tool:

~~~bash
docker compose --profile tools run --rm ingest
~~~

It writes `data/processed/chunks.json` and recreates only `LEGACY_QDRANT_COLLECTION`. It is not part of the online runtime path.

### 3.4 Start API and Streamlit

~~~bash
docker compose up -d --build api streamlit
~~~

Endpoints:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Streamlit: http://localhost:30000
- Qdrant: http://localhost:6333/dashboard
- OpenSearch: http://localhost:9200

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

Run PostgreSQL, Qdrant, and OpenSearch with Docker while running Python locally:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

docker compose up -d postgres qdrant opensearch
python -m scripts.init_sql_data
python -m scripts.migrate_online_indexes
# Run retrieval/evaluation checks, then activate the stable alias.
python -m scripts.migrate_online_indexes --activate-alias
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

### Qwen embedding request fails

- Verify QWEN_EMBEDDING_API_KEY, model name, endpoint, and quota.
- Confirm the API container can reach the configured DashScope endpoint.
- The first successful response must contain exactly 1024 dimensions.
- Default unit tests use MockEmbeddingProvider and do not call the paid API.
- Hugging Face cache is needed only by Legacy ingest or the optional local Reranker.

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

### OpenSearch unavailable or keyword results missing

Check `docker compose logs opensearch`, `OPENSEARCH_URL`, index mapping, and document `index_status`. Graph chat may continue in vector-only mode and returns `metadata.degraded=true`; it must not fall back to `chunks.json`.

### Upload directory is read-only

Ensure the host data directory is writable by Docker. On Linux check ownership and mount options. Do not mount `data/uploads` as read-only.

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

A complete verification requires PostgreSQL, Qdrant, OpenSearch, a Qwen embedding credential, and a working LLM endpoint. Default unit tests remain fully offline through mocks.
