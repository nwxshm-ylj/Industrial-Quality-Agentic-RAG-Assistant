# Industrial Quality Agentic RAG Assistant

> Enterprise-ready industrial quality Agentic RAG reference implementation — FastAPI + LangGraph + Qdrant + PostgreSQL + Streamlit.

面向制造现场质量知识问答、设备异常诊断、规则查询、历史案例检索和结构化数据分析的企业级 RAG 项目。v1.0 将多路 Agent 工作流、混合检索、会话记忆、知识库管理、JWT/RBAC、审计、可观测性、用户反馈和离线评估整合为一套可运行、可演示、可扩展的完整链路。

> 本项目使用演示数据和规则，适合技术验证、作品展示与架构学习。模型输出不能替代现场标准、质量工程师判断或生产审批。

## 业务场景

- 质量工程师查询 FMEA、SOP、检验标准和设备手册。
- 现场人员诊断轮毂识别、OCR、扭矩报警等制造异常。
- 管理人员按自然语言查询检测记录、报警数量和质量趋势。
- 工程师检索历史质量案例、根因和纠正措施。
- 管理员维护企业文档、版本和向量索引。
- 团队通过反馈、评估指标、审计与结构化日志持续改进 RAG 质量。

## 系统架构

~~~mermaid
flowchart LR
    User[Admin / Engineer / Viewer] --> UI[Streamlit]
    User --> API[FastAPI API]
    UI --> API

    API --> Auth[JWT Authentication + RBAC]
    API --> Graph[LangGraph Agentic RAG]
    API --> KB[Knowledge Base Management]
    API --> Feedback[Feedback Service]
    API --> Eval[Evaluation Service]

    Graph --> Memory[Conversation Memory]
    Graph --> Router[Intent Router]
    Router --> Rule[Rule Tool]
    Router --> SQL[Restricted SQL Tool]
    Router --> Case[Case Retriever]
    Router --> Rewrite[Query Rewriter]
    Rewrite --> Hybrid[Hybrid Retriever]
    Hybrid --> Vector[Qdrant Vector Search]
    Hybrid --> Keyword[OpenSearch Keyword Search]
    Hybrid --> Judge[Evidence Judge + Retry]
    Judge --> Generator[Answer Generator]

    Auth --> PG[(PostgreSQL)]
    Memory --> PG
    SQL --> PG
    Case --> PG
    KB --> PG
    KB --> Vector
    KB --> Keyword
    Feedback --> PG
    Eval --> PG
    Eval --> Graph

    API --> Logs[JSON Structured Logs]
    API --> Audit[Operation Audit]
    Audit --> PG
~~~

详细设计见 [Architecture](docs/architecture.md)。

## 核心功能矩阵

| 能力 | 实现 | 企业价值 |
|---|---|---|
| Agentic 路由 | doc_qa、fault_diagnosis、case_search、rule_query、sql_analysis、general | 按问题类型选择最合适的工具和数据源 |
| Hybrid Search | 千问 Embedding + Qdrant Alias + OpenSearch + RRF + 可选 Reranker | 同时覆盖语义召回和工业关键词精确匹配，关键词故障时可降级为 vector-only |
| Evidence Judge | 证据评分、不足时改写并重试 | 降低弱证据直接生成答案的风险 |
| 多轮记忆 | PostgreSQL 按 session_id 保存最近消息 | 支持“那优先排查哪个”等连续追问 |
| Rule Tool | YAML 工业规则匹配 | 处理 PR、配置映射和判定规则 |
| SQL Tool | 白名单、只读 SQL 分析 | 查询质量记录、报警和趋势 |
| Case Retriever | PostgreSQL 历史案例检索 | 复用历史根因和纠正措施 |
| 知识库管理 | md/txt/pdf/docx 上传、版本、删除、重建 | 从脚本入库升级为可管理知识资产 |
| 安全体系 | JWT、PBKDF2 密码哈希、RBAC | 管理用户和高风险操作权限 |
| 审计与可观测性 | request_id、节点 latency、JSON 日志、审计表 | 支持问题定位和操作追溯 |
| 用户反馈 | positive/negative/neutral + comment | 建立真实用户质量信号 |
| RAG 评估 | 意图、来源、关键词、记忆、延迟指标 | 量化版本质量并支持回归比较 |
| 管理界面 | Streamlit 聊天、文档、反馈和评估看板 | 提供完整演示和运营入口 |

## 技术栈

| 层次 | 技术 |
|---|---|
| API | Python 3.11、FastAPI、Pydantic、Uvicorn |
| Agent 编排 | LangGraph、LangChain |
| LLM | OpenAI-compatible API，默认 qwen-plus 配置 |
| 检索 | Qwen text-embedding-v4、Qdrant、OpenSearch、RRF、CrossEncoder |
| 数据 | PostgreSQL、SQLAlchemy、Qdrant、OpenSearch |
| 前端 | Streamlit、Pandas、Requests |
| 安全 | JWT、PBKDF2-SHA256、FastAPI Depends、RBAC |
| 部署 | Docker、Docker Compose |
| 可观测性 | JSON structured logging、request_id、latency、audit log |

## 快速启动

### 前置条件

- Docker Desktop 或 Docker Engine + Compose v2
- 可访问的 OpenAI-compatible LLM
- 千问 Embedding API Key；仅 Legacy ingest 或启用本地 Reranker 时需要 Hugging Face 模型
- 建议至少 8 GB 内存

### 1. 配置环境变量

~~~bash
cp .env.example .env
~~~

Windows PowerShell：

~~~powershell
Copy-Item .env.example .env
~~~

至少修改：

~~~dotenv
LLM_MODEL=qwen-plus
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_EMBEDDING_API_KEY=your_dashscope_api_key
JWT_SECRET_KEY=replace_with_a_long_random_secret
~~~

### 2. Docker Compose 启动

~~~bash
docker compose up -d qdrant postgres opensearch
docker compose --profile tools run --rm init-sql
docker compose run --rm api python -m scripts.migrate_online_indexes
# 先运行检索与评估测试，通过后再切换稳定 Alias
docker compose run --rm api python -m scripts.migrate_online_indexes --activate-alias
docker compose up -d --build api streamlit
~~~

访问：

- Streamlit：http://localhost:30000
- FastAPI Swagger：http://localhost:8000/docs
- Health Check：http://localhost:8000/health
- Qdrant Dashboard：http://localhost:6333/dashboard
- OpenSearch：http://localhost:9200

查看日志：

~~~bash
docker compose logs -f api streamlit
~~~

完整部署、初始化和故障排查见 [Deployment](docs/deployment.md)。

## 默认账号

数据库初始化会幂等创建演示管理员：

| 字段 | 值 |
|---|---|
| Username | admin |
| Password | admin123 |
| Role | admin |

生产环境必须立即修改默认密码和 JWT_SECRET_KEY，并通过密钥管理系统注入敏感配置。

## API 示例

登录：

~~~bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
~~~

将返回的 access_token 保存为 TOKEN，然后调用 graph-chat：

~~~bash
curl -X POST http://localhost:8000/api/v1/graph-chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "轮毂识别异常可能是什么原因？",
    "top_k": 3,
    "session_id": "demo-session-001"
  }'
~~~

关键响应字段包括 answer、citations、request_id、session_id、memory_messages、intent、evidence_score、retry_count 和 metadata.total_latency_ms。

更多登录、上传、反馈和评估请求见 [API Examples](docs/api_examples.md)。

## Streamlit 使用说明

1. 打开 http://localhost:30000。
2. 使用 admin/admin123 登录。
3. 在聊天页选择示例问题或输入现场问题。
4. 查看回答、引用、工具结果、上下文和原始 JSON。
5. 对回答提交有用、无用或一般反馈。
6. 在 Knowledge Base Management 中管理文档。
7. admin/engineer 可进入 RAG Evaluation 查看反馈和评估指标。
8. 点击退出登录清除前端 Token 与用户状态。

界面按角色隐藏未授权操作；后端仍通过 RBAC 强制校验，前端隐藏不能替代服务端授权。

## 知识库管理

支持 md、txt、pdf、docx：

- 文件安全保存至 data/uploads。
- SHA-256 content_hash 防止活跃文档重复上传。
- documents 保存元数据、版本、状态与 chunk 数量。
- document_chunks 保存可追溯分块。
- Qdrant 使用稳定 point ID、版本化 Collection 和稳定 Alias，并按 doc_id 精确删除。
- OpenSearch 保存在线关键词索引，企业检索运行时不依赖 data/processed/chunks.json。
- 支持列表、详情、软删除和原文件重建索引。

Documents are stored with metadata in PostgreSQL and indexed into Qdrant and OpenSearch for online hybrid retrieval.

注意：data/processed/chunks.json 和 scripts/ingest_docs.py 仅保留给 Legacy Demo；scripts/ingest_docs.py 会重建 Legacy Qdrant Collection，不属于企业在线入库流程。

## RBAC 权限矩阵

| 功能 | admin | engineer | viewer |
|---|:---:|:---:|:---:|
| 普通 graph-chat | ✓ | ✓ | ✓ |
| SQL analysis / SQL Tool | ✓ | ✓ | ✗ |
| 查看文档 | ✓ | ✓ | ✓ |
| 上传文档 | ✓ | ✓ | ✗ |
| 删除文档 | ✓ | ✗ | ✗ |
| 重建文档索引 | ✓ | ✗ | ✗ |
| 创建与查看用户 | ✓ | ✗ | ✗ |
| 提交答案反馈 | ✓ | ✓ | ✓ |
| 查看反馈列表与统计 | ✓ | ✓ | ✗ |
| 运行和查看 RAG 评估 | ✓ | ✓ | ✗ |

无 Token 返回 401，角色不足返回 403。权限拒绝会记录结构化日志和 operation_audit_logs。

## 可观测性

每次 graph-chat：

- API 生成 request_id，并通过响应体和 X-Request-ID 返回。
- LangGraph state 贯穿 request_id 与 session_id。
- 主要节点记录 node_name、intent、latency_ms 和 status。
- 响应 metadata 包含 intent、evidence_score、evidence_enough、retry_count、total_latency_ms。
- graph-chat、登录、SQL、文档、反馈、评估和权限拒绝写入审计日志。
- 审计失败只记录错误，不阻断主流程。

~~~bash
docker compose logs -f api
~~~

生产环境可将 JSON 日志采集到 ELK、Loki、OpenSearch 或云日志平台。

## 用户反馈与 RAG 评估

反馈保存 request_id、session_id、用户、问题、回答、rating、comment、intent、citations 和 metadata。admin/engineer 可按评分过滤、查看正负向比例和意图分布。

评估读取 data/eval/eval_questions.json，指标包括：

- intent_accuracy
- source_hit_rate
- answer_keyword_hit_rate
- memory_followup_success_rate
- avg_latency_ms

~~~bash
python -m scripts.evaluate_system
python -m scripts.test_feedback_evaluation
~~~

API 评估报告写入 PostgreSQL 的 rag_eval_runs、rag_eval_items，并输出 data/eval/eval_report_<run_id>.json。

## 测试命令

先启动 PostgreSQL、Qdrant、OpenSearch，并在隔离的演示环境初始化数据库和在线索引：

~~~bash
python -m scripts.init_sql_data
python -m scripts.migrate_online_indexes

python -m scripts.test_auth_rbac
python -m scripts.test_document_management
python -m scripts.test_memory
python -m scripts.test_observability
python -m scripts.test_feedback_evaluation
python -m scripts.test_graph
~~~

工具与检索专项验证：

~~~bash
python -m scripts.test_rule_tool
python -m scripts.test_sql_tool
python -m scripts.test_case_tool
python -m scripts.test_hybrid_retriever
python -m scripts.test_embedding_provider_mock
python -m scripts.test_qdrant_vector_backend
python -m scripts.test_opensearch_keyword_backend
python -m scripts.test_rrf_fusion
python -m scripts.test_online_hybrid_retriever
python -m scripts.test_index_activation_guard
python -m scripts.test_llm
~~~

发布前静态检查：

~~~bash
python -m compileall app scripts
git diff --check
~~~

Docker 内验证：

~~~bash
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_memory
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_feedback_evaluation
~~~

## 项目亮点

- 不是单一路径的“向量检索 + LLM”，而是可解释的多路 Agentic 工作流。
- 将 Rule、SQL、Case 和 Document RAG 放入统一 LangGraph state。
- 同时覆盖语义召回、关键词召回、证据判断和重试。
- 从离线脚本扩展到带版本、状态和删除能力的知识库管理。
- JWT/RBAC 在前后端一致执行，SQL 和索引操作有独立授权边界。
- request_id、节点耗时、审计、用户反馈和离线评估形成质量闭环。
- 保留 raw_docs 脚本流程，兼顾演示初始化和企业增量入库。
- 提供完整 Docker Compose、演示脚本和面试讲解材料。

## 项目结构

~~~text
.
├── app/
│   ├── api/          # Auth、Chat、Documents、Feedback、Evaluation
│   ├── core/         # Config、Security、Dependencies、Logger
│   ├── graph/        # LangGraph state、workflow、nodes
│   ├── memory/       # PostgreSQL conversation memory
│   ├── rag/          # Loader、Splitter、Hybrid Retrieval、Generation
│   ├── schemas/      # Pydantic API schemas
│   ├── services/     # Auth、Audit、Document、Feedback、Evaluation
│   └── tools/        # Rule、SQL、Case tools
├── data/
│   ├── raw_docs/
│   ├── uploads/
│   ├── processed/
│   ├── rules/
│   └── eval/
├── docs/
├── scripts/
├── ui/
├── docker-compose.yml
└── Dockerfile
~~~

## 文档导航

- [系统架构](docs/architecture.md)
- [部署指南](docs/deployment.md)
- [API 示例](docs/api_examples.md)
- [完整 Demo 脚本](docs/demo_script.md)
- [面试讲解笔记](docs/interview_notes.md)

## Roadmap

- [ ] PostgreSQL/Qdrant schema migration 工具与版本化发布。
- [ ] 异步文档入库和评估任务队列。
- [ ] 多租户、部门级数据隔离和细粒度文档 ACL。
- [ ] OpenTelemetry tracing、Prometheus metrics 和集中日志方案。
- [ ] 增加 indexing_jobs、后台入库进度和失败任务重试。
- [ ] RAGAS/LLM-as-a-Judge、基准集版本和趋势对比。
- [ ] Prompt、模型和索引版本治理及 A/B 测试。
- [ ] 对象存储、病毒扫描、文件配额和生命周期管理。
- [ ] CI/CD、依赖锁定、镜像签名和安全扫描。
- [ ] 流式响应、任务进度和更完整的运营后台。

## License

[MIT](LICENSE)
