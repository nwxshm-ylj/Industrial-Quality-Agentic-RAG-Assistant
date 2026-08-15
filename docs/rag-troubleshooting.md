# RAG 质量与可观测性标准排障手册

## 1. 文档目的

本文给出 Industrial Quality Agentic RAG Assistant 的标准排障流程，适用于以下问题：

- 回答出现无依据内容或疑似幻觉；
- 正确文档没有被召回；
- 召回结果相关但排名靠后；
- 引用来源错误或缺失；
- 多轮追问理解错误；
- OpenSearch、Reranker 或记忆系统发生降级；
- graph-chat 延迟升高；
- 模型调用量或成本异常。

排障原则：先保存现场，再定位请求；先判断路由和检索，再判断生成；先验证数据和索引，再调整模型。

```text
请求失败或回答异常
→ request_id 定位
→ intent / rewritten_query 检查
→ degraded / retrieval_mode 检查
→ Context 与 Citation 检查
→ Qdrant / OpenSearch / Reranker 检查
→ Evidence Judge 检查
→ Prompt / Answer Generator 检查
→ Memory 检查
→ 离线评估与回归
```

## 2. 当前排障入口

| 服务 | 默认地址 | 用途 |
|---|---|---|
| React | http://localhost:30080 | 用户界面与运营后台 |
| FastAPI | http://localhost:18000 | API、Swagger、健康检查、指标 |
| Swagger | http://localhost:18000/docs | 查看接口定义 |
| Qdrant | http://localhost:6333 | 向量 Collection、Alias、Point |
| Grafana | http://localhost:3000 | 统一看板、日志和 Trace |
| Prometheus | http://localhost:9090 | 指标查询 |
| Tempo | http://localhost:3200 | Trace 后端，通常从 Grafana 查询 |
| Loki | http://localhost:3100 | 日志后端，通常从 Grafana查询 |

OpenSearch 当前没有映射宿主机端口，应通过 `docker compose exec opensearch` 在容器内部查询。

关键代码：

- `app/core/logger.py`：节点结构化日志；
- `app/core/metrics.py`：Prometheus 指标；
- `app/core/telemetry_context.py`：请求级遥测上下文；
- `app/services/usage_service.py`：请求、模型、检索事件持久化；
- `app/rag/graph_chain.py`：graph-chat 汇总 metadata 和用量；
- `app/rag/online_hybrid_retriever.py`：检索计数、组件耗时和降级；
- `app/graph/nodes/evidence_judge_node.py`：证据判断；
- `app/evaluation/retrieval_evaluator.py`：独立检索评估；
- `app/evaluation/ragas_evaluator.py`：RAGAS 语义评估。

## 3. 第零步：确认环境和服务状态

在项目根目录执行：

```powershell
Set-Location C:\cursor-projects\2-Industrial-RAG
docker compose ps
```

如果同时启用了可观测性栈：

```powershell
docker compose `
  -f docker-compose.yml `
  -f docker-compose.observability.yml `
  ps
```

检查 API 存活和就绪：

```powershell
curl.exe http://localhost:18000/health/live
curl.exe http://localhost:18000/health/ready
```

预期：

- `/health/live` 返回 API 进程存活；
- `/health/ready` 中 PostgreSQL、Qdrant、模型配置、OpenSearch 等关键项为 ready；
- Redis、Neo4j、DeepDOC 等可选模块根据配置显示 ready 或 disabled；
- readiness 不应调用真实收费 Embedding API。

查看异常容器：

```powershell
docker compose ps --all
docker compose logs --tail 200 api
docker compose logs --tail 200 postgres
docker compose logs --tail 200 qdrant
docker compose logs --tail 200 opensearch
```

如果可观测性栈异常：

```powershell
docker compose `
  -f docker-compose.yml `
  -f docker-compose.observability.yml `
  logs --tail 200 prometheus grafana tempo loki otel-collector alloy
```

## 4. 第一步：复现请求并保存现场

### 4.1 登录并保存 Token

以下命令适用于 Windows PowerShell：

```powershell
$API_BASE = "http://localhost:18000"

$loginBody = @{
  username = "admin"
  password = "admin123"
} | ConvertTo-Json

$login = Invoke-RestMethod `
  -Method Post `
  -Uri "$API_BASE/api/v1/auth/login" `
  -ContentType "application/json" `
  -Body $loginBody

$TOKEN = $login.access_token
$headers = @{ Authorization = "Bearer $TOKEN" }
```

生产环境不得继续使用默认账号密码。

### 4.2 发起可复现请求

固定问题、session_id 和 top_k：

```powershell
$sessionId = "troubleshoot-wheel-001"
$chatBody = @{
  question = "轮毂识别异常优先排查什么？"
  session_id = $sessionId
  top_k = 5
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod `
  -Method Post `
  -Uri "$API_BASE/api/v1/graph-chat" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $chatBody

$REQUEST_ID = $response.request_id
$response | ConvertTo-Json -Depth 30
```

保存现场：

```powershell
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$response |
  ConvertTo-Json -Depth 30 |
  Out-File "data/eval/incident-$timestamp-$REQUEST_ID.json" -Encoding utf8
```

至少保存这些字段：

```text
request_id
session_id
question
answer
intent
rewritten_query
contexts
citations
evidence_score
evidence_enough
retry_count
metadata.total_latency_ms
metadata.retrieval_mode
metadata.degraded
metadata.degraded_reason
metadata.degraded_components
metadata.vector_result_count
metadata.keyword_result_count
metadata.reranker_degraded
```

禁止只保存最终答案。没有 Context、Citation 和 metadata，就无法区分检索问题和生成问题。

## 5. 第二步：按 request_id 查询完整调用情况

admin 和 engineer 可以查询：

```powershell
$requestUsage = Invoke-RestMethod `
  -Method Get `
  -Uri "$API_BASE/api/v1/observability/requests/$REQUEST_ID" `
  -Headers $headers

$requestUsage | ConvertTo-Json -Depth 30
```

响应包含：

- `request`：请求汇总；
- `ai_events`：LLM、Embedding 调用；
- `retrieval_events`：检索组件明细。

按 request_id 查询 API 日志：

```powershell
docker compose logs api --since 30m |
  Select-String $REQUEST_ID
```

只看节点完成和错误：

```powershell
docker compose logs api --since 30m |
  Select-String $REQUEST_ID |
  Select-String 'node_name|status|error_message|latency_ms'
```

如果 request 中存在 `trace_id`：

1. 打开 http://localhost:3000；
2. 进入 Explore；
3. 选择 Tempo 数据源；
4. 按 trace_id 查询；
5. 展开 `langgraph.*`、`retrieval.*` 和 `ai.*` Span。

## 6. 第三步：判断是不是路由问题

先检查：

```powershell
$response.intent
$response.rewritten_query
$response.rule_result
$response.sql_result
$response.case_result
```

意图对应关系：

| 问题类型 | 预期 intent | 预期路径 |
|---|---|---|
| 文档、诊断、标准规则 | `rag` | Query Rewrite → Retrieve → Evidence Judge |
| 统计、设备、告警记录查询 | `sql` | SQL Tool |
| 历史案例与风险追溯 | `rag` + `query_features.traceability_required=true` | Unified Hybrid Retriever + Neo4j enrichment |
| 普通交流 | `general` | Generate |

典型判断：

- 文档标准数值问题进入 `sql`：检查 SQL 实体与操作双重门禁；
- Intent 正确但 rewritten_query 丢失设备型号：Query Rewrite 问题；
- viewer 访问 SQL 分析返回 403：权限行为，不是 RAG 故障；
- 追溯问题没有 Neo4j 增强：检查 metadata.query_features.traceability_required。

检查最近意图分布：

```powershell
Invoke-RestMethod `
  -Uri "$API_BASE/api/v1/observability/analytics/intents" `
  -Headers $headers |
  ConvertTo-Json -Depth 10
```

如果某次发布后大量问题突然集中到一个 intent，优先检查 Intent Router Prompt 或模型配置。

## 7. 第四步：判断是不是检索降级

检查：

```powershell
$response.metadata.retrieval_mode
$response.metadata.degraded
$response.metadata.degraded_reason
$response.metadata.degraded_components
$response.metadata.reranker_degraded
$response.metadata.vector_result_count
$response.metadata.keyword_result_count
```

判断规则：

| 现象 | 初步结论 |
|---|---|
| `degraded=false` | 双路检索没有报告降级 |
| `degraded_components` 包含 `keyword` | OpenSearch 失败，降级到 vector-only |
| `reranker_degraded=true` | Reranker 失败，返回 Fusion 结果 |
| vector 数量为 0 | Qdrant、Alias、过滤或向量问题 |
| keyword 数量为 0 | OpenSearch、索引、分词或过滤问题 |
| 两路都有结果但 Context 不相关 | Query、Chunk、融合或精排问题 |

查询最近七天检索汇总：

```powershell
Invoke-RestMethod `
  -Uri "$API_BASE/api/v1/observability/analytics/retrieval" `
  -Headers $headers |
  ConvertTo-Json -Depth 10
```

注意：当前实现只要任一组件降级，`retrieval_mode` 可能被概括为 `vector_only`。排障时必须同时看 `degraded_components`、`reranker_degraded` 和两路结果数量。

## 8. 第五步：人工检查 Context 与 Citation

查看前五条 Context：

```powershell
$response.contexts |
  Select-Object `
    doc_id, chunk_id, source, doc_type, version, `
    score, vector_score, keyword_score, rrf_score, `
    weighted_score, rerank_score, final_score_type, text |
  Format-List
```

查看引用：

```powershell
$response.citations |
  Select-Object `
    doc_id, chunk_id, source, page_number, `
    retrieval_source, score, vector_score, keyword_score, `
    rrf_score, weighted_score, rerank_score, final_score_type |
  Format-Table -AutoSize
```

根据结果分类：

### A. 正确证据完全不在 Context

属于召回问题，继续检查文档、Chunk、Qdrant、OpenSearch、过滤和 Embedding。

### B. 正确证据在 Context，但排名靠后

属于排序问题，检查 RRF、权重、候选池和 Reranker。

### C. Context 正确，但答案出现无依据结论

属于生成侧 Faithfulness 问题，检查 Prompt、模型、记忆污染和拒答策略。

### D. Context 正确、回答有依据，但没有回答当前问题

属于 Response Relevancy 或多轮指代问题，检查 Query Rewrite 和 Memory。

## 9. 第六步：检查 PostgreSQL 文档和 Chunk

### 9.1 查看文档状态

```powershell
docker compose exec postgres sh -lc `
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT doc_id, filename, doc_type, version, status, chunk_count, failed_stage, left(error_message, 120) AS error_message, updated_at FROM documents ORDER BY updated_at DESC LIMIT 20;"'
```

重点检查：

- `status` 是否为 `indexed`；
- `chunk_count` 是否大于 0；
- `failed_stage` 是否为 qdrant/opensearch/chunk/parse；
- version 和 doc_type 是否符合过滤条件。

### 9.2 搜索目标知识是否进入 Chunk

```powershell
docker compose exec postgres sh -lc `
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT doc_id, chunk_id, chunk_index, source, left(text, 300) AS text FROM document_chunks WHERE text ILIKE ''%轮毂%'' ORDER BY doc_id, chunk_index LIMIT 30;"'
```

如果这里都找不到目标内容，问题发生在：

```text
原文档缺失
或解析失败
或 OCR/表格内容丢失
或 Chunk 策略切坏
```

此时不要先调整 Embedding。

### 9.3 检查 Chunk 数量一致性

```powershell
docker compose exec postgres sh -lc `
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT d.doc_id, d.filename, d.chunk_count AS declared_chunks, COUNT(dc.id) AS actual_chunks FROM documents d LEFT JOIN document_chunks dc ON dc.doc_id = d.doc_id WHERE d.status = ''indexed'' GROUP BY d.doc_id, d.filename, d.chunk_count HAVING d.chunk_count <> COUNT(dc.id);"'
```

有返回结果说明 PostgreSQL 文档元数据和 Chunk 表不一致。

## 10. 第七步：检查 Qdrant 向量索引

### 10.1 查看 Alias

```powershell
Invoke-RestMethod http://localhost:6333/aliases |
  ConvertTo-Json -Depth 10
```

确认：

```text
industrial_docs_active
→ industrial_docs_bge_m3_1024_v1
```

### 10.2 查看 Collection

```powershell
Invoke-RestMethod `
  http://localhost:6333/collections/industrial_docs_bge_m3_1024_v1 |
  ConvertTo-Json -Depth 10
```

检查：

- Collection 存在；
-向量维度为 1024；
- points_count 不为 0；
- Alias 指向当前 BGE-M3 Collection。

### 10.3 按 doc_id 查看 Point

先从 PostgreSQL 或 Citation 中取得 doc_id：

```powershell
$DOC_ID = "替换为真实doc_id"

$qdrantBody = @{
  filter = @{
    must = @(
      @{ key = "doc_id"; match = @{ value = $DOC_ID } },
      @{ key = "index_status"; match = @{ value = "indexed" } }
    )
  }
  limit = 20
  with_payload = $true
  with_vector = $false
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:6333/collections/industrial_docs_active/points/scroll" `
  -ContentType "application/json" `
  -Body $qdrantBody |
  ConvertTo-Json -Depth 20
```

检查 Payload：

```text
doc_id
chunk_id
text
source
version
index_status
embedding_model
embedding_dimension
embedding_index_version
parser_version
chunk_strategy
```

常见问题：

- PostgreSQL 有 Chunk，但 Qdrant 没 Point：向量入库失败或索引版本错误；
- Point 存在但 `index_status=staging`：双索引发布未完成；
- dimension 不是 1024：Collection 与 BGE-M3 不兼容；
- Alias 指向旧 Collection：迁移或发布流程错误；
- doc_id/version 不匹配：文档重建残留或过滤条件错误。

禁止为了排障直接删除完整 Collection。

## 11. 第八步：检查 OpenSearch 关键词索引

### 11.1 查看集群和索引

```powershell
docker compose exec opensearch `
  curl -s http://localhost:9200/_cluster/health?pretty

docker compose exec opensearch `
  curl -s http://localhost:9200/_cat/indices?v
```

默认关键词索引名：

```text
industrial_docs_keyword_v1
```

### 11.2 查询目标关键词

```powershell
docker compose exec opensearch `
  curl -s -X POST `
  http://localhost:9200/industrial_docs_keyword_v1/_search?pretty `
  -H 'Content-Type: application/json' `
  -d '{"size":5,"query":{"bool":{"filter":[{"term":{"index_status":"indexed"}}],"must":[{"match":{"text":"轮毂识别异常"}}]}}}'
```

检查：

- hits 是否大于 0；
- `_source.doc_id` 是否正确；
- `_source.chunk_id` 是否与 PostgreSQL/Qdrant 一致；
- `index_status` 是否为 indexed；
- 技术编号、故障码、设备型号是否被正确命中。

如果自然语言能命中，但设备编号不能命中，需要检查 analyzer、keyword 字段或精确匹配策略。

## 12. 第九步：检查 Reranker

检查 API 容器环境：

```powershell
docker compose exec api sh -lc 'echo USE_RERANKER=$USE_RERANKER; echo RERANKER_MODEL=$RERANKER_MODEL; echo RERANKER_FAIL_OPEN=$RERANKER_FAIL_OPEN'
```

当前 Compose 默认 `USE_RERANKER=false`。如果没有显式启用，系统只执行 Fusion，不执行 BGE Reranker。

查看请求结果：

```powershell
$response.metadata.reranker_degraded
$response.metadata.reranker_latency_ms
$response.citations |
  Select-Object source, rrf_score, weighted_score, rerank_score, final_score_type
```

判断：

- `rerank_score` 为空：Reranker 未运行；
- `reranker_degraded=true`：Reranker 运行失败并 fail-open；
- Reranker 运行后正确文档排名下降：模型不适配或候选文本过长；
- `reranker_latency_ms` 很高：检查设备、模型加载和候选数量。

## 13. 第十步：检查 Evidence Judge

查看：

```powershell
$response.evidence_score
$response.evidence_enough
$response.retry_count
$response.contexts |
  Select-Object source, evidence_signal_score, score, final_score_type
```

当前逻辑是：

```python
evidence_score = max(context.evidence_signal_score)
evidence_enough = evidence_score >= 0.55
```

需要注意：

- RRF 路径优先使用原始 vector_score；
- keyword-only 可能使用原始 BM25 分数；
- Weighted Fusion 使用 0～1 的归一化分数；
- Reranker 使用 CrossEncoder 原始输出；
- 不同分数并不是同一量纲；
- 0.55 是经验阈值，不是概率。

因此：

- `evidence_enough=true` 不代表答案必然正确；
- `evidence_enough=false` 不代表所有 Context 都无关；
- 阈值异常应在标注集上按 `final_score_type` 分别校准；
- 不应只根据一条线上样例修改阈值。

## 14. 第十一步：判断生成幻觉

只有在 Context 已经正确时，才进入生成侧排查。

逐句检查答案：

1. 每个事实是否能在 Context 中找到依据；
2. 数值、型号、步骤、告警码是否与原文一致；
3. 是否把“可能原因”写成“确定原因”；
4. 是否增加了停线、放行、更换部件等高风险动作；
5. Citation 是否指向实际支持该结论的 Chunk；
6. 是否混入了历史会话内容；
7. 是否在证据不足时仍给出确定性结论。

查看模型调用：

```powershell
$requestUsage.ai_events |
  Select-Object component, operation, provider, model, status, latency_ms, input_tokens, output_tokens, total_tokens, error_type |
  Format-Table -AutoSize
```

查看 Prompt 版本：

```powershell
$response.metadata.prompt_release
$response.metadata.prompt_versions
```

如果 Context 正确但回答无依据，重点检查：

- `app/rag/generator.py`；
- `prompts/` 中当前 Prompt 版本；
- Prompt Release 配置；
- LLM 模型和温度；
- Context 是否在 Prompt 组装时被截断；
- Prompt 是否明确要求基于参考资料回答；
- 是否要求证据不足时拒答。

## 15. 第十二步：检查多轮记忆污染

先使用全新的 session_id 重试：

```powershell
$freshBody = @{
  question = "轮毂识别异常优先排查什么？"
  session_id = "fresh-$([guid]::NewGuid().ToString('N'))"
  top_k = 5
} | ConvertTo-Json

$freshResponse = Invoke-RestMethod `
  -Method Post `
  -Uri "$API_BASE/api/v1/graph-chat" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $freshBody
```

对比原 session 和新 session：

```powershell
$response.memory_messages | Format-List
$freshResponse.memory_messages | Format-List
$response.rewritten_query
$freshResponse.rewritten_query
```

查询 PostgreSQL 会话消息：

```powershell
docker compose exec postgres sh -lc `
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT session_id, role, left(content, 200) AS content, intent, created_at FROM conversation_messages ORDER BY created_at DESC LIMIT 30;"'
```

如果新 session 正确、旧 session 错误，重点检查：

- session_id 是否被多个用户复用；
- 历史消息是否包含错误答案；
- Query Rewrite 是否过度引用历史内容；
- Redis 缓存是否与 PostgreSQL 不一致；
- 长期记忆是否错误召回其他会话；
- owner_key、username 和 session 隔离。

## 16. 第十三步：延迟排查

### 16.1 请求汇总

```powershell
Invoke-RestMethod `
  -Uri "$API_BASE/api/v1/observability/analytics/overview" `
  -Headers $headers |
  ConvertTo-Json -Depth 10
```

### 16.2 Prometheus 查询

Graph P95：

```powershell
$query = [uri]::EscapeDataString(
  'histogram_quantile(0.95, sum(rate(industrial_rag_graph_duration_seconds_bucket[5m])) by (le))'
)
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query" |
  ConvertTo-Json -Depth 20
```

各节点 P95：

```powershell
$query = [uri]::EscapeDataString(
  'histogram_quantile(0.95, sum(rate(industrial_rag_node_duration_seconds_bucket[5m])) by (le,node_name))'
)
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query" |
  ConvertTo-Json -Depth 20
```

检索降级率：

```powershell
$query = [uri]::EscapeDataString(
  'sum(rate(industrial_rag_retrieval_degraded_total[10m])) / clamp_min(sum(rate(industrial_rag_retrieval_requests_total[10m])),0.001)'
)
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query" |
  ConvertTo-Json -Depth 20
```

模型 P95：

```powershell
$query = [uri]::EscapeDataString(
  'histogram_quantile(0.95, sum(rate(industrial_rag_model_duration_seconds_bucket[5m])) by (le,provider,model,operation))'
)
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query" |
  ConvertTo-Json -Depth 20
```

### 16.3 按组件解释延迟

| 慢的组件 | 优先检查 |
|---|---|
| load_memory | PostgreSQL、Redis、长期记忆检索 |
| intent_router | LLM 网络、Prompt 长度 |
| query_rewriter | LLM 网络、历史消息长度 |
| Qdrant | Collection、过滤、资源、网络 |
| OpenSearch | JVM、Index、查询和资源 |
| Fusion | 候选数量、去重 |
| Reranker | 模型设备、候选数量、文本长度 |
| Generate | LLM 首 Token、输入/输出 Token |
| save_memory | PostgreSQL、Redis、后台任务队列 |

## 17. 第十四步：运行独立检索评估

检索质量不能从 `vector_hit_count` 推断，必须使用带相关性标注的数据集。

默认数据集：

```text
data/eval/retrieval_eval_questions.json
```

运行：

```powershell
docker compose exec api python -m scripts.evaluate_retrieval `
  --top-k 5 `
  --k-values 1,3,5
```

最小 Smoke Test：

```powershell
docker compose exec api python -m scripts.evaluate_retrieval `
  --top-k 5 `
  --k-values 1,3,5 `
  --max-questions 1
```

报告：

```text
data/eval/retrieval_eval_report.json
data/eval/retrieval_eval_report_<run_id>.json
```

指标解释：

| 结果 | 结论 |
|---|---|
| Recall@20 低 | 正确证据没有进入候选集 |
| Recall@20 高、Recall@5 低 | 排序问题 |
| Recall 高、Precision 低 | 噪声多、Chunk 或过滤问题 |
| Recall 高、MRR 低 | 正确结果排名靠后 |
| nDCG 低 | 整体排序质量差 |
| P95/P99 高 | 检索尾延迟问题 |

## 18. 第十五步：运行生成质量评估

RAGAS 指标：

| 指标 | 定位问题 |
|---|---|
| Context Precision | 召回结果中有多少真正相关 |
| Context Recall | 必要证据是否完整召回 |
| Response Relevancy | 回答是否针对问题 |
| Faithfulness | 回答是否得到 Context 支持 |

通过 API 运行小规模 RAGAS：

```powershell
$ragasBody = @{
  max_questions = 5
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "$API_BASE/api/v1/evaluation/ragas/run" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $ragasBody |
  ConvertTo-Json -Depth 30
```

判断：

- Context Recall 低：先修检索；
- Context Precision 低：修过滤、Chunk、融合或 Reranker；
- Context 指标高但 Faithfulness 低：修生成 Prompt；
- Faithfulness 高但 Response Relevancy 低：修问题理解和 Prompt；
- 四项都低：数据、检索和生成可能同时有问题。

RAGAS 依赖 Judge LLM，存在成本和波动，不进入默认离线单元测试。

## 19. 第十六步：查询反馈闭环

查看反馈统计：

```powershell
Invoke-RestMethod `
  -Uri "$API_BASE/api/v1/feedback/stats" `
  -Headers $headers |
  ConvertTo-Json -Depth 20
```

查看负向反馈：

```powershell
Invoke-RestMethod `
  -Uri "$API_BASE/api/v1/feedback?rating=negative&limit=100" `
  -Headers $headers |
  ConvertTo-Json -Depth 30
```

建议按以下维度聚类：

```text
intent
doc_type
retrieval_mode
degraded
prompt_release
embedding_index_version
问题类型
失败原因
```

用户负向反馈是质量线索，不是严格 Ground Truth。必须回到 Context、Citation 和领域标注确认原因。

## 20. 问题分类与处理矩阵

| 症状 | 主要证据 | 优先排查 | 不要先做 |
|---|---|---|---|
| 无 Context | context_count=0 | 索引、过滤、服务 | 调 Prompt |
| 向量无结果 | vector_hit_count=0 | Alias、维度、Point | 调 LLM |
| 关键词无结果 | keyword_hit_count=0 | OpenSearch、分词、索引 | 换 Embedding |
| 正确文档未进 Top20 | Recall@20 低 | 数据、解析、Chunk、Embedding | 调 Reranker |
| 正确文档在 Top20 不在 Top5 | Recall@20 高、MRR 低 | Fusion、Reranker | 重做解析 |
| Context 噪声多 | Precision 低 | Chunk、过滤、Reranker | 提高 top_k |
| Context 正确但答案编造 | Faithfulness 低 | Prompt、模型、拒答 | 改召回权重 |
| 回答忠实但答非所问 | Relevancy 低 | Query Rewrite、Prompt、Memory | 删除文档 |
| 新 session 正常、旧 session 错 | memory_messages 差异 | 会话和长期记忆 | 重建知识库 |
| total_latency 高 | 节点 P95 | 最慢节点 | 盲目扩容全部服务 |
| 线上突然普遍下降 | 按版本聚合 | Prompt/索引/模型发布 | 逐条手工修答案 |

## 21. 修复后的回归验证

快速检查：

```powershell
python -m compileall app scripts
python -m scripts.test_metrics
python -m scripts.test_observability_stack
python -m scripts.test_retrieval_evaluation
python -m scripts.test_ragas_evaluation
git diff --check
```

依赖 PostgreSQL、Qdrant 和 OpenSearch：

```powershell
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_usage_analytics
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.evaluate_retrieval --top-k 5 --k-values 1,3,5
```

还需要执行：

- 修复前问题的单条复现；
- 相邻问题和反例；
- 同 session 多轮追问；
- 全新 session 对照；
- OpenSearch 降级演练；
- Reranker 关闭/开启对照；
- 修复前后同一版本化评估集对比。

真实 LLM、RAGAS Judge、在线多模态和收费 API 不应放进默认单元测试。

## 22. 事故记录模板

```markdown
# RAG 质量事故记录

## 基本信息
- 时间：
- request_id：
- trace_id：
- session_id：
- username/role：
- 问题：
- 实际答案：
- 预期答案：

## 版本信息
- Git Commit：
- Prompt Release：
- LLM：
- Embedding Model：
- Embedding Index Version：
- Qdrant Alias Target：
- OpenSearch Index：
- Reranker：
- Parser Version：
- Chunk Strategy：

## 请求信息
- intent：
- rewritten_query：
- evidence_score：
- evidence_enough：
- retry_count：
- retrieval_mode：
- degraded：
- degraded_reason：

## 检索信息
- vector_hit_count：
- keyword_hit_count：
- fused_hit_count：
- returned_count：
- 预期 doc_id/chunk_id：
- 实际 Top K：

## 延迟
- total_latency_ms：
- qdrant_latency_ms：
- opensearch_latency_ms：
- fusion_latency_ms：
- reranker_latency_ms：
- generate latency：

## 根因分类
- [ ] 数据缺失
- [ ] 文档解析
- [ ] Chunk
- [ ] Query Rewrite
- [ ] Embedding
- [ ] Qdrant
- [ ] OpenSearch
- [ ] Fusion
- [ ] Reranker
- [ ] Evidence Judge
- [ ] Prompt/Generation
- [ ] Memory
- [ ] 外部服务降级

## 修复与验证
- 修复内容：
- 新增测试：
- 修复前指标：
- 修复后指标：
- 回滚方案：
```

## 23. 最终判断标准

一次排障完成必须满足：

1. 能通过 request_id 找到请求、检索和模型调用；
2. 能明确问题属于路由、检索、排序、生成、记忆或服务降级；
3. 能给出复现条件，而不是只描述现象；
4. 能用 Context/Citation 或标注数据证明根因；
5. 修复不依赖删除整个 Qdrant Collection 或绕过安全机制；
6. 修复后有自动化测试或版本化评估样例；
7. 修复前后使用相同数据集和配置对比；
8. 记录 Prompt、Embedding、索引、Parser 和 Chunk 版本；
9. 不把 `evidence_score` 当成事实正确率；
10. 不把返回数量当成 Recall。

## 24. 错误拒答专项诊断

先确认环境一致，再判断阈值。不要看到拒答就直接降低 `EVIDENCE_CONFIDENCE_THRESHOLD`。

```powershell
curl.exe http://localhost:8000/health/ready

docker compose exec api python -m scripts.diagnose_retrieval_evidence `
  --question-id STD005 `
  --output data/eval/diagnostic_STD005.json
```

诊断报告会展示：

- 当前 Embedding provider/model/dimension/index version；
- Qdrant 物理 Collection、Alias 及实际目标；
- 目标来源在 Vector、Keyword、最终融合结果中的排名；
- Evidence Judge 的 confidence、reasons、missing_aspects 和 abstain_reason；
- 各阶段候选的来源、chunk、分数和文本预览。

典型根因与处理顺序：

1. Alias 指向不同模型的集合：先修环境，禁止调阈值；
2. Vector 与 Keyword 均未命中：检查解析、chunk、入库和评测标注；
3. 前两路命中但融合后丢失：检查 RRF、候选数和邻接扩展；
4. 正确证据进入最终上下文但被拒答：检查 missing_aspects、覆盖率和阈值；
5. 回答正文已经明确“资料未提供”，但 metadata 未标记拒答：检查语义拒答分类；
6. 问题明确指向“未上传/未收录”的目标：应在 Evidence Judge 确定性拒答，不能用相似文档补齐不存在的事实。
