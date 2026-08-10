# 项目代码走读与技术讲解指南

> 文件名为兼容既有 README 链接而保留。本文只用于项目技术理解和代码走读，不包含简历包装或虚构业务指标。

## 1. 一句话说明

这是一个把工业文档问答、确定性规则、受限 SQL、历史案例、知识图谱和多轮记忆统一到 LangGraph 状态机中的工业质量 Agentic RAG 系统。

## 2. 建议理解顺序

### 第一层：请求入口

先阅读：

1. `app/main.py`：应用启动、中间件、readiness 和 Router 注册。
2. `app/api/routes_chat.py`：Bearer Token、同步 graph-chat、SSE 流式响应和审计。
3. `app/schemas/chat.py`：请求过滤、多模态输入、引用和响应兼容字段。

需要理解：request_id 在哪里生成，user/role 如何进入 Graph State，401/403/500 如何区分。

### 第二层：Agent 工作流

阅读：

1. `app/rag/graph_chain.py`
2. `app/graph/state.py`
3. `app/graph/workflow.py`
4. `app/graph/nodes/`

核心问题：

- 为什么先加载记忆再判断意图？
- 为什么 Rule 未命中回退 RAG？
- 为什么 Evidence Judge 只允许一次重写？
- 为什么所有路径都必须经过 generate 和 save_memory？

### 第三层：离线知识加工

阅读：

1. `app/services/document_service.py`
2. `app/rag/loader.py`
3. `app/rag/parsing/contracts.py`
4. `app/rag/parsing/router.py`
5. `app/rag/chunking/layout_chunker.py`
6. `app/rag/splitter.py`

重点追踪一个文件从上传到 indexed 的全过程，并识别 staging、promotion、failed_stage 和补偿清理。

### 第四层：在线检索

阅读：

1. `app/rag/retriever.py`
2. `app/rag/online_hybrid_retriever.py`
3. `app/rag/embeddings/local_provider.py`
4. `app/rag/search_backends/qdrant_backend.py`
5. `app/rag/search_backends/opensearch_backend.py`
6. `app/rag/fusion.py`
7. `app/rag/reranker.py`

重点理解 BGE-M3 Provider 为什么进程级复用、Qdrant 为什么查询 Alias、RRF 为什么只依赖排名、OpenSearch 故障如何降级。

### 第五层：记忆与生成

阅读：

1. `app/memory/conversation_memory.py`
2. `app/memory/short_term.py`
3. `app/memory/long_term.py`
4. `app/memory/layered_memory.py`
5. `app/rag/generator.py`
6. `app/prompting/registry.py`

重点区分：PostgreSQL 原始会话、Redis 短期窗口、抽取式摘要、Qdrant/OpenSearch 情景记忆，以及它们的降级关系。

## 3. 五条核心技术链路

### 文档问答

```text
load_memory → intent_router → query_rewriter → retrieve
→ evidence_judge → generate → save_memory
```

### 规则查询

```text
intent_router → rule_tool
  ├─ 命中 → generate
  └─ 未命中 → query_rewriter → RAG
```

### SQL 分析

```text
intent_router → RBAC 检查 → 模板 SQL/LLM SQL
→ SELECT/表白名单/LIMIT 校验 → PostgreSQL → generate
```

### 文档上传

```text
save → parse → merge → chunk → PostgreSQL
→ Qdrant staging + OpenSearch staging
→ promotion → indexed
```

### 分层记忆

```text
PostgreSQL 原始消息
+ Redis 最近窗口/摘要
+ Qdrant 语义记忆/OpenSearch 全文记忆
→ 统一 memory_messages
```

## 4. 关键设计取舍

### 为什么使用 LangGraph

系统具有多意图、工具分支、规则回退、证据重试和统一收尾，不是固定 retrieve → generate。显式图比嵌套 if/else 更易观测和测试。

### 为什么使用 Qdrant + OpenSearch

向量检索擅长语义改写，OpenSearch 擅长 PR 编码、VIN、故障码、设备编号和精确术语。两路分数尺度不同，默认 RRF 使用排名融合，避免直接相加。

### 为什么本地使用 BGE-M3

运行时不产生 Embedding API 费用，也不受网络和配额影响；固定模型 Revision、维度和版本化 Collection 后更容易复现与回滚。代价是 API 容器需要模型内存，CPU 冷启动延迟较高。

### 为什么 Chunk 保留章节、页码和表头

切得过小会丢失语义，切得过大会引入噪声。layout-token-v2 以标题和表格为边界，控制最大 token，并让每个 Chunk 单独进入 Prompt 时仍然可理解和可引用。

### 为什么 PostgreSQL 仍是记忆最终存储

Redis 有 TTL，向量/全文索引可能暂时不可用。原始消息先落 PostgreSQL，短期和长期检索层可以重建或降级，不会因为缓存故障丢失会话事实。

## 5. 必须准确说明的能力边界

- 当前证据判断是规则阈值，不是独立训练的奖励模型。
- 短期摘要是抽取式拼接截断，不是 LLM 语义总结。
- 长期记忆是问答情景检索，不是完整的用户画像或事实记忆系统。
- 知识图谱只增强历史案例路径，不参与所有文档问题。
- 多模态和 DeepDOC 是否可用取决于配置与本地模型资源，不能只根据代码存在就宣称已启用。
- 内置检索集只有少量样例，指标适合做回归，不代表真实工厂效果。
- `chunks.json` 和旧 BM25 Retriever 是 Legacy 兼容资产，不是当前在线 Hybrid Search 数据源。

## 6. 推荐动手验证

```powershell
python -m compileall app scripts
python -m scripts.test_local_embedding_provider
python -m scripts.test_document_parsing
python -m scripts.test_layout_chunker
python -m scripts.test_online_hybrid_retriever
python -m scripts.test_retrieval_evaluation
docker compose config --quiet
git diff --check
```

集成环境：

```powershell
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_memory
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_feedback_evaluation
docker compose exec api python -m scripts.evaluate_retrieval
```

真实 LLM、RAGAS、多模态 Embedding 和 DeepDOC 模型测试不应放入默认单元测试，应在显式配置好外部资源后单独验收。
