# Industrial Quality Agentic RAG Assistant

面向制造现场质量知识、设备异常诊断、结构化数据分析和企业文档管理的 Agentic RAG 系统。系统以 FastAPI 提供接口，使用 LangGraph 编排意图路由、规则查询、历史案例检索、受限 SQL 分析和混合文档检索，并提供 PostgreSQL 会话记忆、JSON 结构化日志及 Streamlit 管理界面。

> 当前仓库内置的是可运行的演示数据与规则，不应直接作为生产质量决策系统使用。模型输出仍需结合现场标准和人工复核。

## 核心能力

- Agentic 路由：支持 `doc_qa`、`fault_diagnosis`、`case_search`、`rule_query`、`sql_analysis` 和 `general`。
- 工业文档问答：支持 Markdown、TXT、PDF、DOCX，覆盖 FMEA、SOP、OCR 规则等知识。
- 混合检索：融合 Qdrant 向量检索与本地 BM25，可选 CrossEncoder 重排。
- 规则、案例与 SQL 工具：支持 YAML 规则匹配、PostgreSQL 历史案例查询和受限只读分析。
- 证据评估与重试：证据不足时扩展查询并最多重试一次。
- 多轮会话记忆：按 `session_id` 保存最近对话，支持指代补全和连续追问。
- JWT 与 RBAC：提供 admin、engineer、viewer 角色控制及 PostgreSQL 操作审计。
- 企业知识库管理：支持上传、元数据、版本、增量入库、删除、文档列表和索引重建。
- 可观测性：每次 graph-chat 返回 `request_id` 和 `metadata`，主要节点输出包含耗时与状态的 JSON 日志。
- Streamlit：提供聊天、引用、工具结果、评估报告和 Knowledge Base Management 界面。
- 离线评估与集成验证：提供 graph、memory、observability 和 document management 测试脚本。

## 工作流程

~~~text
用户 / Streamlit
       |
    FastAPI 生成 request_id
       |
    load_memory(session_id)
       |
    Intent Router
       |
       +-- general ------------------------------> generate
       +-- rule_query --> Rule Tool
       |                    +-- 命中 ------------> generate
       |                    +-- 未命中 --> 文档 RAG
       +-- sql_analysis --> SQL Tool ------------> generate
       +-- case_search --> Case Retriever -------> generate
       +-- doc_qa / fault_diagnosis
                              |
                         Query Rewriter
                              |
                 Qdrant 向量检索 + BM25
                              |
                  加权融合 + 可选 Reranker
                              |
                     Evidence Judge / Retry
                              |
                           generate
                              |
                    save_memory -> response
~~~

响应保留原有 `intent`、`evidence_score` 等顶层字段，并额外返回 `request_id` 和 `metadata.total_latency_ms`。默认混合检索权重为向量 0.65、BM25 0.35，融合分数过滤阈值为 0.15，证据充分阈值为 0.55。

企业文档入库链路：

~~~text
Upload -> 安全文件名 / SHA-256 去重 -> 多格式解析 -> Chunk
       -> PostgreSQL documents/document_chunks
       -> Qdrant 稳定 point ID
       -> chunks.json 同步（BM25）
~~~

## 技术栈

- Python 3.11、FastAPI、Uvicorn、Streamlit
- LangChain、LangGraph、OpenAI 兼容聊天模型接口
- Sentence Transformers：BAAI/bge-small-zh-v1.5
- Qdrant、BM25、可选 BAAI/bge-reranker-base
- PostgreSQL、SQLAlchemy
- Docker Compose

## 项目结构

~~~text
.
├── app/
│   ├── api/                 # Chat 与文档管理 FastAPI 路由
│   ├── core/                # 环境配置、JSON structured logger
│   ├── db/                  # SQLAlchemy 连接
│   ├── graph/               # LangGraph 状态、工作流和节点
│   ├── memory/              # session_id 会话记忆
│   ├── rag/                 # Loader、切分、Qdrant、BM25、重排和生成
│   ├── schemas/             # Chat 与 Document 请求/响应模型
│   ├── services/            # DocumentService
│   └── tools/               # Rule、Case、SQL 工具
├── data/
│   ├── raw_docs/            # 旧版 Markdown 批量入库源文件
│   ├── uploads/             # 企业文档上传文件（运行时创建）
│   ├── processed/           # BM25 chunks.json
│   ├── rules/               # YAML 工业规则
│   └── eval/                # 评估集与评估报告
├── scripts/                 # 初始化、入库、评估和集成验证脚本
├── ui/                      # Streamlit 前端
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
~~~

## 快速启动：Docker Compose

### 1. 配置模型服务

复制环境变量模板：

~~~powershell
Copy-Item .env.example .env
~~~

至少设置有效的 LLM_API_KEY。默认配置使用阿里云百炼的 OpenAI 兼容接口和 qwen-plus；也可以替换为其他 OpenAI 兼容服务：

~~~dotenv
LLM_MODEL=qwen-plus
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
~~~

### 2. 启动基础设施

~~~bash
docker compose up -d qdrant postgres
~~~

### 3. 初始化演示数据库和知识库

~~~bash
docker compose --profile tools run --rm init-sql
docker compose --profile tools run --rm ingest
~~~

> init-sql 会删除并重建三张演示业务表（inspection_record、equipment_alarm、quality_cases），并幂等创建会话与文档管理表；ingest 会删除并重建配置的 Qdrant collection。不要对生产数据库或已有向量索引直接执行这两个命令。

首次入库会下载 Hugging Face 嵌入模型，耗时取决于网络和机器性能。

### 4. 启动 API 和界面

~~~bash
docker compose up -d --build api streamlit
~~~

启动后访问：

- Streamlit：http://localhost:30000
- FastAPI 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

查看日志：

~~~bash
docker compose logs -f api streamlit
~~~

停止服务：

~~~bash
docker compose down
~~~

如需同时删除 Qdrant、PostgreSQL 和模型缓存卷，可执行 docker compose down -v。该操作会永久删除容器卷数据。

## 本地开发

要求：Python 3.11、可用的 Docker、可访问的 LLM 接口。以下方式仅在 Docker 中运行 Qdrant 和 PostgreSQL，应用在宿主机运行。

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Copy-Item .env.example .env
# 编辑 .env，填写 LLM_API_KEY 等配置

docker compose up -d qdrant postgres
python -m scripts.init_sql_data
python -m scripts.ingest_docs
~~~

启动 API：

~~~powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
~~~

在另一个终端启动前端：

~~~powershell
.\.venv\Scripts\Activate.ps1
streamlit run ui/streamlit_app.py
~~~

本地前端默认请求 http://127.0.0.1:8000/api/v1/graph-chat，也可以通过 RAG_API_URL 覆盖。

## 配置项

| 变量 | 默认值 | 说明 |
|---|---|---|
| QDRANT_URL | http://localhost:6333 | Qdrant 地址 |
| QDRANT_COLLECTION | industrial_docs | 文档向量 collection |
| EMBEDDING_MODEL | BAAI/bge-small-zh-v1.5 | 嵌入模型 |
| LLM_MODEL | qwen-plus | 聊天模型名称 |
| LLM_API_KEY | 无，必填 | OpenAI 兼容接口密钥 |
| LLM_BASE_URL | DashScope 兼容接口 | OpenAI 兼容接口地址 |
| DATABASE_URL | 本地 PostgreSQL 连接串 | SQLAlchemy 数据库地址 |
| RERANKER_MODEL | BAAI/bge-reranker-base | CrossEncoder 重排模型 |
| USE_RERANKER | 代码默认 true | 是否启用重排；.env.example 和 Compose 默认关闭 |
| RAG_API_URL | 本地 graph-chat 接口 | Streamlit 请求的 API 地址 |
| LOG_LEVEL | INFO | JSON 结构化日志级别 |
| JWT_SECRET_KEY | dev_secret_key_change_me | JWT 签名密钥；生产环境必须修改 |
| JWT_ALGORITHM | HS256 | JWT 签名算法 |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 1440 | Access Token 有效期（分钟） |

建议首次运行保持 USE_RERANKER=false，确认完整链路可用后再启用重排模型。

## Authentication and RBAC

系统使用 JWT Bearer Token 强制保护 `/api/v1/graph-chat` 和全部文档管理接口。密码使用带随机 salt 的 PBKDF2-SHA256 哈希保存，JWT 密钥和有效期从环境变量读取。

### 默认管理员

初始化数据库会在用户不存在时创建：

- username: `admin`
- password: `admin123`
- role: `admin`

> 默认账号仅用于首次启动。生产环境必须立即修改默认密码，并将 `JWT_SECRET_KEY` 设置为随机高强度密钥；禁止继续使用代码中的开发默认值。

登录：

~~~bash
curl -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}"
~~~

成功后将 `access_token` 放入请求头：

~~~text
Authorization: Bearer <access_token>
~~~

管理员还可以使用：

- `POST /api/v1/auth/users`：创建 admin、engineer 或 viewer；
- `GET /api/v1/auth/users`：查看用户列表。

### 权限矩阵

| 操作 | admin | engineer | viewer |
|---|---:|---:|---:|
| graph-chat 普通问答 | ✓ | ✓ | ✓ |
| SQL analysis / SQL Tool | ✓ | ✓ | ✗ |
| 查看文档列表与详情 | ✓ | ✓ | ✓ |
| 上传文档 | ✓ | ✓ | ✗ |
| 删除文档 | ✓ | ✗ | ✗ |
| 重建文档索引 | ✓ | ✗ | ✗ |
| 创建和查看用户 | ✓ | ✗ | ✗ |

viewer 的 `sql_analysis` 会在 SQL Tool 执行前返回 403，不会访问数据库。

### 操作审计

`operation_audit_logs` 记录登录成功/失败、graph-chat、SQL Tool、文档上传/删除/重建以及权限拒绝。审计字段包括 request_id、session_id、username、role、action、resource 和 status。审计写入失败只输出结构化错误日志，不中断主请求。

Streamlit 登录后保存 access token 和用户角色；viewer 只显示文档列表，engineer 可上传，admin 可执行全部管理操作。

## API

### 健康检查

~~~http
GET /health
~~~

### 基础 RAG

~~~http
POST /api/v1/chat
Content-Type: application/json

{
  "question": "轮毂识别异常可能是什么原因？",
  "top_k": 3
}
~~~

该接口保留原有单轮混合检索行为。

### Agentic RAG、多轮记忆与可观测性

~~~http
POST /api/v1/graph-chat
Content-Type: application/json

{
  "question": "轮毂识别异常可能是什么原因？",
  "top_k": 3,
  "session_id": "quality-session-001"
}
~~~

继续使用相同 `session_id` 发送“那优先排查哪个？”，系统会加载最近 6 条历史消息辅助意图识别、查询改写和答案生成。省略 `session_id` 时使用 `default`。

成功响应中的关键字段：

~~~json
{
  "request_id": "8a456cf7-...",
  "session_id": "quality-session-001",
  "answer": "...",
  "citations": [],
  "memory_messages": [],
  "intent": "fault_diagnosis",
  "evidence_score": 0.78,
  "evidence_enough": true,
  "retry_count": 0,
  "metadata": {
    "intent": "fault_diagnosis",
    "evidence_score": 0.78,
    "evidence_enough": true,
    "retry_count": 0,
    "total_latency_ms": 1320.45
  }
}
~~~

每个主要 LangGraph 节点均输出 JSON 日志，字段包括 `request_id`、`session_id`、`node_name`、`intent`、`latency_ms` 和 `status`。查看容器日志：

~~~bash
docker compose logs -f api
~~~

## Knowledge Base Management

支持 `.md`、`.txt`、`.pdf`、`.docx` 上传，以及元数据、版本、增量索引、列表、软删除和重建索引。Streamlit 的 **Knowledge Base Management** Tab 提供对应管理操作。

Documents are stored with metadata in PostgreSQL, indexed into Qdrant for vector search, and synchronized to chunks.json for BM25 retrieval.

### 数据流与状态

- 上传文件保存在 `data/uploads/`，文件名经过安全处理。
- SHA-256 `content_hash` 用于避免重复上传。
- PostgreSQL `documents` 保存文档元数据，`document_chunks` 保存分块。
- Qdrant point ID 由 `doc_id + chunk_id` 稳定生成；删除仅过滤指定 `payload.doc_id`。
- 企业 chunks 与没有 `doc_id` 的 legacy raw_docs chunks 合并写入 `data/processed/chunks.json`。
- 文档状态为 `uploaded`、`indexed`、`failed` 或 `deleted`。

### 文档管理端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/v1/documents/upload | FormData 上传并建立索引 |
| GET | /api/v1/documents | 默认列出未删除文档；可用 `?status=deleted` 过滤 |
| GET | /api/v1/documents/{doc_id} | 查询文档详情 |
| POST | /api/v1/documents/{doc_id}/reindex | 从保存的原文件重建索引 |
| DELETE | /api/v1/documents/{doc_id} | 删除 Qdrant points/chunks 并软删除 metadata |

上传示例：

~~~bash
curl -X POST http://localhost:8000/api/v1/documents/upload -F "file=@./example.txt" -F "doc_type=SOP" -F "version=v1"
~~~

其他操作：

~~~bash
curl http://localhost:8000/api/v1/documents
curl http://localhost:8000/api/v1/documents/{doc_id}
curl -X POST http://localhost:8000/api/v1/documents/{doc_id}/reindex
curl -X DELETE http://localhost:8000/api/v1/documents/{doc_id}
~~~

> 上传、删除和重建会立即更新 Qdrant 与 chunks.json。当前 API 进程中的 BM25 实例在启动时加载 chunks.json；如需让 BM25 内存索引读取最新企业文档，请重启 API。Qdrant 向量检索不受此限制。

## 数据与知识库维护

### 旧版 raw_docs 批量入库

`scripts.ingest_docs` 保留用于首次构建演示知识库：

1. 将 UTF-8 Markdown 文件放入 `data/raw_docs/`。
2. 文件名包含 fmea、sop 或 rule 时，分别标记为 FMEA、SOP、RULE；其他文件为 GENERAL。
3. 执行：

~~~bash
python -m scripts.ingest_docs
~~~

脚本使用 500 字符 chunk、80 字符重叠，写入 `data/processed/chunks.json`，并重建整个 Qdrant collection。它适合初始化演示数据；企业增量文档请使用文档管理 API。重新运行该脚本会重建 collection，已有企业文档需要通过 reindex 接口重新写入 Qdrant。

### 企业文档管理

上传、列表、删除和重建请使用 `/api/v1/documents` 或 Streamlit 管理 Tab。文档操作会记录 `upload_start`、`file_saved`、`document_parsed`、`chunks_created`、`postgres_written`、`qdrant_written`、`document_indexed`、`document_deleted`、`document_reindexed` 和 `error` 等结构化事件。

### 修改规则

编辑 `data/rules/industrial_rules.yaml`。规则工具通过 PR 编码和关键词匹配，修改后需要重启 API。

### 初始化 PostgreSQL

~~~bash
python -m scripts.init_sql_data
~~~

脚本会重建并填充三张演示业务表：

- `inspection_record`：AI 视觉检测记录；
- `equipment_alarm`：设备报警记录；
- `quality_cases`：历史质量案例。

并幂等创建或保留：

- `conversation_messages`：session_id 多轮消息；
- `documents`：企业文档元数据与状态；
- `document_chunks`：企业文档 chunks。
- `users`：用户、密码哈希、角色和启用状态；
- `operation_audit_logs`：登录、权限与业务操作审计。

> 该命令会删除并重建三张演示业务表，执行前务必确认 `DATABASE_URL` 指向正确环境。

## 验证与评估

仓库中的测试文件是可直接执行的集成验证脚本，不是 pytest 测试套件。运行前应启动 PostgreSQL、Qdrant，完成数据库初始化，并配置可用的 LLM/Embedding 服务。

核心回归：

~~~bash
python -m scripts.test_auth_rbac
python -m scripts.test_graph
python -m scripts.test_memory
python -m scripts.test_observability
python -m scripts.test_document_management
~~~

工具与检索验证：

~~~bash
python -m scripts.test_llm
python -m scripts.test_rule_tool
python -m scripts.test_sql_tool
python -m scripts.test_case_tool
python -m scripts.test_hybrid_retriever
~~~

Docker 容器内验证：

~~~bash
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_memory
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_document_management
~~~

运行完整离线评估：

~~~bash
python -m scripts.evaluate_system
~~~

问题来自 `data/eval/eval_questions.json`，结果写入 `data/eval/eval_report.json`，并可在 Streamlit 的“评估报告”页查看。历史报告只代表特定模型、数据和环境，应以本地重新评估结果为准。

## 实现说明与限制

- 多个模型和检索组件在模块导入阶段初始化，首次启动可能需要较长时间和较多内存。
- BM25 使用简单的英文/数字 token 与中文单字、bigram，不包含专业分词或词典。
- chunks.json 会在企业文档操作后更新，但当前进程中的 BM25 内存索引需要重启 API 才会重新加载。
- `scripts.ingest_docs` 会重建 Qdrant collection；它不是企业增量更新命令。
- 意图识别优先调用 LLM，失败时使用关键词规则兜底；案例条件提取和规则匹配仍以关键词为主。
- SQL 工具仅允许 SELECT、白名单表和最大 LIMIT 100；生产环境仍应使用只读账号、独立 schema、查询超时和审计。
- 会话记忆按 `session_id` 存储最近消息，但尚未实现租户级隔离、过期清理和容量治理。
- API 已实现 JWT 与角色级 RBAC，但尚未提供 Refresh Token、主动 Token 吊销、MFA、限流和流式输出。
- 文档权限目前是接口级角色控制，没有租户、部门或单文档级 ACL。
- 依赖和容器镜像未锁定精确版本，生产部署前应增加 lockfile、固定镜像版本和自动化测试。
- contexts、SQL 行、历史案例和会话消息可能包含敏感业务数据，生产环境应进行脱敏和权限控制。

## License

[MIT](LICENSE)
