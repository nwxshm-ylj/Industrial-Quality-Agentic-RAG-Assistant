# Docker Compose 部署指南

## 1. 环境要求

- Docker Desktop 或 Docker Engine + Compose v2；
- 建议至少 16GB 内存；启用 BGE Reranker、DeepDOC 或多模态时需要更多资源；
- 首次下载 BGE-M3 和调用在线 LLM 时需要网络；
- `data/` 目录必须可写，模型、上传文件、评估报告通过卷持久化；
- Windows 建议使用 PowerShell 7 或系统 PowerShell。

默认端口：

| 服务 | 地址 |
|---|---|
| React | http://localhost:30080 |
| Streamlit | http://localhost:30000 |
| FastAPI | http://localhost:18000 |
| DeepDOC Runtime | http://localhost:18010 |
| PostgreSQL | localhost:5432 |
| Qdrant | http://localhost:6333 |
| OpenSearch | http://localhost:9200 |
| Redis | localhost:6379 |
| Neo4j Browser | http://localhost:7474 |

## 2. 环境变量

```powershell
Copy-Item .env.example .env
```

必须修改：

```dotenv
LLM_MODEL=qwen-plus
LLM_API_KEY=替换为真实密钥
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
JWT_SECRET_KEY=替换为足够长的随机值
POSTGRES_PASSWORD=替换为强密码
DATABASE_URL=postgresql+psycopg2://rag_user:URL编码后的密码@postgres:5432/industrial_rag
```

本地文本 Embedding：

```dotenv
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL_NAME=BAAI/bge-m3
LOCAL_EMBEDDING_MODEL_PATH=/app/data/models/bge-m3
LOCAL_EMBEDDING_MODEL_REVISION=5617a9f61b028005a4858fdac845db406aefb181
LOCAL_EMBEDDING_DIMENSION=1024
LOCAL_EMBEDDING_BATCH_SIZE=8
LOCAL_EMBEDDING_DEVICE=cpu
LOCAL_EMBEDDING_NORMALIZE_EMBEDDINGS=true
QDRANT_COLLECTION=industrial_docs_bge_m3_1024_v1
QDRANT_COLLECTION_ALIAS=industrial_docs_active
EMBEDDING_INDEX_VERSION=bge-m3-1024-v1
```

在线 Hybrid Search：

```dotenv
OPENSEARCH_URL=http://opensearch:9200
OPENSEARCH_INDEX_PREFIX=industrial_docs
KEYWORD_SEARCH_BACKEND=opensearch
HYBRID_DEGRADED_MODE=vector_only
RETRIEVAL_FUSION_STRATEGY=rrf
RETRIEVAL_RRF_K=60
USE_RERANKER=true
RERANKER_MODEL=BAAI/bge-reranker-base
```

分层记忆：

```dotenv
LAYERED_MEMORY_ENABLED=true
REDIS_URL=redis://redis:6379/0
MEMORY_SHORT_TERM_TTL_SECONDS=86400
MEMORY_SHORT_TERM_MAX_MESSAGES=20
MEMORY_RECENT_LIMIT=6
MEMORY_LONG_TERM_LIMIT=4
MEMORY_SEMANTIC_SCORE_THRESHOLD=0.45
MEMORY_QDRANT_COLLECTION=industrial_memory_bge_m3_1024_v1
MEMORY_INDEX_VERSION=bge-m3-v1
```

不要提交真实 `.env`。生产环境应使用 Docker Secret、Kubernetes Secret 或企业密钥管理服务。

## 3. 下载本地 BGE-M3

模型不会在 API 启动或请求期间自动下载。执行一次：

```powershell
docker compose run --rm api python -m scripts.download_local_embedding_model --destination /app/data/models/bge-m3
```

下载脚本固定 Hugging Face Revision，并写入 `MODEL_PROVENANCE.json`。检查：

```powershell
Get-Content data/models/bge-m3/MODEL_PROVENANCE.json
```

切换现有 `.env`：

```powershell
python -m scripts.configure_local_embedding --env-file .env
```

## 4. 启动基础服务

```powershell
docker compose up -d postgres qdrant opensearch redis neo4j
docker compose ps
```

初始化 PostgreSQL：

```powershell
docker compose --profile tools run --rm init-sql
```

`scripts/init_sql_data.py` 会创建业务、文档、用户、审计、记忆、反馈、评估和用量表。该脚本包含样例数据初始化；在生产数据库执行前必须审查，不应把它当成通用数据库迁移工具。

## 5. 构建在线双索引

先构建新物理 Collection，不切换 Alias：

```powershell
docker compose run --rm api python -m scripts.migrate_online_indexes
```

执行独立检索验收：

```powershell
docker compose run --rm -e USE_RERANKER=false api python -m scripts.evaluate_retrieval
```

只有迁移成功、Qdrant/OpenSearch 数量一致且召回符合预期，才切换 Alias：

```powershell
docker compose run --rm api python -m scripts.migrate_online_indexes --activate-alias
```

迁移脚本不会删除旧 Collection。新索引为空、双路数量不一致或迁移失败时不会切换 Alias。

## 6. 启动应用

不启用 DeepDOC：

```powershell
docker compose up -d --build api react-web streamlit
```

启用独立 DeepDOC Runtime：

```powershell
docker compose --profile deepdoc up -d --build
```

DeepDOC 需要提前准备本地源码和模型：

```powershell
python -m scripts.prepare_deepdoc_runtime `
  --source-root "<包含 deepdoc、rag 和 api 的 service/core 目录>"
```

运行时目录：

- `data/deepdoc_runtime/source/`
- `data/models/deepdoc-runtime-res/rag/res/deepdoc/`

DeepDOC 容器强制离线模式，不在请求期间下载模型。缺少模型文件时 readiness 会显示 disabled、degraded 或 unavailable，具体取决于配置。

## 7. 健康检查

```powershell
curl.exe http://localhost:18000/health
curl.exe http://localhost:18000/health/ready
```

readiness 重点检查：

- PostgreSQL；
- Qdrant Alias；
- 本地 Embedding 模型目录；
- Prompt Registry；
- OpenSearch；
- Redis、Neo4j；
- DeepDOC Runtime。

readiness 不调用真实 Embedding 推理，也不会触发收费 API。

## 8. 初始化可选数据

同步质量案例到 Neo4j：

```powershell
docker compose exec api python -m scripts.sync_quality_case_graph
```

多模态索引迁移与 Alias 激活应使用独立脚本，并在非空验证后执行：

```powershell
docker compose exec api python -m scripts.migrate_advanced_rag
docker compose exec api python -m scripts.activate_multimodal_index
```

## 9. 可观测性栈

```powershell
docker compose `
  -f docker-compose.yml `
  -f docker-compose.observability.yml `
  up -d
```

主要端口：Grafana 3000、Prometheus 9090、Loki 3100、Tempo 3200、OTLP 4317/4318。

## 10. 常用测试

快速离线检查：

```powershell
python -m compileall app scripts
python -m scripts.test_local_embedding_provider
python -m scripts.test_document_parser_contract
python -m scripts.test_layout_chunker
python -m scripts.test_online_hybrid_retriever
python -m scripts.test_layered_memory
python -m scripts.test_retrieval_evaluation
docker compose config --quiet
git diff --check
```

集成测试：

```powershell
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_memory
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_feedback_evaluation
```

## 11. 常见故障

### API readiness 显示 LocalEmbeddingModelMissing

确认 `data/models/bge-m3` 已下载，并且容器内路径是 `/app/data/models/bge-m3`。

### Qdrant UnexpectedResponse 或 Alias 不存在

先运行 `scripts.migrate_online_indexes`，校验新索引，再运行 `--activate-alias`。不要直接删除整个 Qdrant 数据卷。

### OpenSearch 不可用

检查容器 health、JVM 内存和 `OPENSEARCH_URL`。在线问答会按配置降级为 vector-only，并在 metadata 标记 degraded，禁止回退 chunks.json。

### 首次检索很慢

本地 BGE-M3 和 Reranker 首次加载存在冷启动。BGE-M3 已本地化；Reranker 也应提前下载并挂载，避免生产请求触发网络下载。

### DeepDOC 容器退出

检查挂载路径和必需模型文件；不要把 `PASSWORD` 等无关变量传给 Neo4j 或 DeepDOC。使用：

```powershell
docker compose logs --tail 200 deepdoc-runtime
```

### PostgreSQL 密码修改后连接失败

已有 volume 不会因修改环境变量自动重置数据库密码。必须让数据库内部用户密码与 DATABASE_URL 一致，且特殊字符需要 URL 编码。不要直接删除生产 volume。

## 12. 生产安全要求

- 修改默认 admin 密码和 JWT_SECRET_KEY；
- 使用 TLS 和反向代理；
- 限制 CORS、上传大小和外部 URL；
- PostgreSQL、Qdrant、OpenSearch、Redis、Neo4j 不直接暴露公网；
- 模型和 Prompt 使用固定版本；
- 使用数据库迁移工具替代样例初始化脚本；
- 配置备份、恢复、日志脱敏、数据保留和告警规则；
- 发布前记录当前 Qdrant Alias 目标，准备回滚到旧 Collection。
