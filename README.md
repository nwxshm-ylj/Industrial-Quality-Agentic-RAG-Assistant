# Industrial Agentic RAG

面向制造现场质量知识、设备异常诊断和结构化数据分析的 Agentic RAG 示例项目。系统使用 FastAPI 提供接口，以 LangGraph 编排意图识别、规则查询、历史案例检索、受限 SQL 分析和文档 RAG，并提供 Streamlit 可视化界面。

> 当前仓库内置的是可运行的演示数据与规则，不应直接作为生产质量决策系统使用。模型输出仍需结合现场标准和人工复核。

## 核心能力

- 工业文档问答：检索 FMEA、SOP、OCR 规则等 Markdown 文档。
- 故障诊断：按可能原因、排查步骤和处理建议组织回答。
- 混合检索：融合 Qdrant 向量检索与本地 BM25，可选 CrossEncoder 重排。
- 规则查询：从 YAML 规则库中匹配 PR 配置和故障排查规则。
- 历史案例检索：按缺陷类型、工位从 PostgreSQL 查询质量案例。
- 自然语言数据分析：优先使用固定 SQL 模板，未命中时由 LLM 生成受白名单限制的只读查询。
- 证据评估与重试：证据不足时扩展查询并最多重试一次。
- 可观测结果：返回意图、改写查询、证据分数、引用、上下文和工具调用结果。
- 离线评估：内置 11 个覆盖主要路由的评估问题和报告生成脚本。

## 工作流程

~~~text
用户 / Streamlit
       |
    FastAPI
       |
    意图识别
       |
       +-- general ------------------------------> 答案
       +-- rule_query --> Rule Tool
       |                    +-- 命中 ------------> LLM 生成
       |                    +-- 未命中 --> 文档 RAG
       +-- sql_analysis --> SQL Tool ------------> LLM 生成
       +-- case_search --> Case Tool ------------> LLM 生成
       +-- doc_qa / fault_diagnosis
                              |
                           查询改写
                              |
             Qdrant 向量检索 + 本地 BM25
                              |
                 加权融合 + 可选 Reranker
                              |
                         证据充分性判断
                              |
              不足时改写并重试一次 --> LLM 生成
~~~

默认混合检索权重为向量 0.65、BM25 0.35，融合分数过滤阈值为 0.15。Agentic 流程使用 0.55 作为当前版本的证据充分阈值。

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
│   ├── api/                 # FastAPI 路由
│   ├── core/                # 环境配置
│   ├── db/                  # SQLAlchemy 连接
│   ├── graph/               # LangGraph 状态、工作流和节点
│   ├── rag/                 # 切分、向量库、BM25、重排和生成
│   ├── schemas/             # 请求与响应模型
│   └── tools/               # Rule、Case、SQL 工具
├── data/
│   ├── raw_docs/            # Markdown 原始知识文档
│   ├── processed/           # chunks.json
│   ├── rules/               # YAML 工业规则
│   └── eval/                # 评估集与评估报告
├── scripts/                 # 入库、数据库初始化、评估和验证脚本
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

> init-sql 会删除并重建三张业务表，然后写入随机演示数据；ingest 会删除并重建配置的 Qdrant collection。不要对已有生产数据执行这两个命令。

首次入库会下载 Hugging Face 嵌入模型，耗时取决于网络和机器性能。

### 4. 启动 API 和界面

~~~bash
docker compose up -d api streamlit
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

建议首次运行保持 USE_RERANKER=false，确认完整链路可用后再启用重排模型。

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

该接口仅执行混合检索和答案生成。

### Agentic RAG

~~~http
POST /api/v1/graph-chat
Content-Type: application/json

{
  "question": "最近一周ZP8工位误识别数量是多少？",
  "top_k": 3
}
~~~

top_k 取值范围为 1 到 10。Agentic 接口会根据意图选择规则、SQL、案例或文档检索路径。

~~~bash
curl -X POST http://localhost:8000/api/v1/graph-chat \
  -H "Content-Type: application/json" \
  -d '{"question":"PR001对应什么轮毂配置？","top_k":3}'
~~~

主要响应字段：

- answer：最终回答。
- citations：来源、文档类型、chunk 和各阶段分数。
- intent、rewritten_query：路由意图与实际检索查询。
- evidence_score、evidence_enough、retry_count：证据判断信息。
- rule_result、sql_result、case_result：工具调用结果。
- contexts：最终送入生成模型的上下文；可能包含业务数据。

## 数据与知识库维护

### 添加文档

1. 将 UTF-8 编码的 Markdown 文件放入 data/raw_docs/。当前加载器只扫描该目录第一层的 Markdown 文件。
2. 文件名包含 fmea、sop 或 rule 时，会分别标记为 FMEA、SOP、RULE；其他文件标记为 GENERAL。
3. 重新执行入库：

~~~bash
python -m scripts.ingest_docs
~~~

脚本使用 500 字符 chunk、80 字符重叠，生成 data/processed/chunks.json，同时重建 Qdrant collection。API 启动时会将 chunks 加载到 BM25 内存索引，因此重新入库后需要重启 API。

### 修改规则

编辑 data/rules/industrial_rules.yaml。当前规则工具通过 PR 编码和关键词匹配，修改后需要重启 API。

### 初始化结构化数据

~~~bash
python -m scripts.init_sql_data
~~~

脚本会重建并填充：

- inspection_record：AI 视觉检测记录；
- equipment_alarm：设备报警记录；
- quality_cases：历史质量案例。

该命令用于演示环境，执行前务必确认 DATABASE_URL 指向正确的数据库。

## 验证与评估

仓库中的测试文件是可直接执行的集成验证脚本，并非 pytest 测试套件：

~~~bash
python -m scripts.test_llm
python -m scripts.test_rule_tool
python -m scripts.test_sql_tool
python -m scripts.test_case_tool
python -m scripts.test_hybrid_retriever
python -m scripts.test_graph
~~~

运行完整评估：

~~~bash
python -m scripts.evaluate_system
~~~

问题来自 data/eval/eval_questions.json，结果写入 data/eval/eval_report.json，并可在 Streamlit 的“评估报告”页查看。仓库当前保存的示例报告包含 11 个问题，记录的总体通过率为 100%、平均延迟为 8.224 秒；这是特定模型、数据和运行环境下的历史结果，应以本地重新评估结果为准。

## 实现说明与限制

- 多个模型和检索组件在模块导入阶段初始化，首次启动可能需要较长时间和较多内存。
- BM25 使用简单的英文/数字 token 与中文单字、bigram，不包含专业分词或词典。
- 意图识别优先调用 LLM，失败时使用关键词规则兜底；案例条件提取和规则匹配目前也是关键词实现。
- SQL 工具仅允许 SELECT、白名单表和最大 LIMIT 100，但校验基于正则表达式，不等同于完整 SQL 解析或数据库级安全隔离。生产环境应使用只读账号、独立 schema、查询超时和审计。
- API 当前没有认证、授权、限流、会话记忆或流式输出。
- 依赖和容器镜像未锁定精确版本，生产部署前应增加 lockfile、固定镜像版本并建立自动化测试。
- contexts、SQL 行和历史案例会返回给客户端，可能包含敏感生产信息。

## License

[MIT](LICENSE)
