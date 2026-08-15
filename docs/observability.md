# 企业可观测性与用量分析

## 1. 信号模型

系统通过 request_id 和 trace_id 关联四类信号：

| 信号 | 存储/后端 | 作用 |
|---|---|---|
| Trace | OpenTelemetry Collector、Tempo | 查看一次请求和依赖调用树 |
| Metric | Prometheus | 请求率、错误率、延迟、降级率、模型用量 |
| Log | JSON stdout、Alloy、Loki | 搜索具体节点、错误和业务事件 |
| Usage Fact | PostgreSQL | Token、成本、意图、检索和质量分析 |

Telemetry 后端故障不能让 graph-chat 失败。用量事实使用独立事务和有界后台任务池；队列满时记录 `usage_persist_queue_full`，不允许无限占用内存。

## 2. 关联标识

- `request_id`：API 与业务请求主标识；
- `trace_id`：OpenTelemetry Trace 标识；
- `span_id`：单个 Graph 节点或依赖调用；
- `session_id`：会话记忆标识；
- `username/role`：审计主体。

request_id、session_id、username 属于高基数字段，不应作为 Prometheus Label；它们保存在 Trace、Log、审计表和 PostgreSQL 明细中。

## 3. 节点耗时

`app/core/logger.py::observe_node` 包装主要节点：

- load_memory；
- intent_router；
- query_rewriter；
- retrieve；
- evidence_judge；
- rule_tool；
- sql_tool；
- generate；
- save_memory；
- graph_chat。

结构化日志至少包含 request_id、session_id、node_name、intent、latency_ms 和 status。

## 4. 用量数据

### rag_request_runs

每次 graph-chat 或模型相关 API 一条汇总，保存路由、状态、总延迟、意图、证据、检索模式、降级状态、Token 和估算成本。

### ai_usage_events

每次 LLM 或 Embedding 调用一条事件。document embedding 和 query embedding 使用不同 operation。缺少 Provider Usage 时保持 unavailable，不伪造 Token。

### retrieval_events

每次文档检索保存 vector/keyword/fused 数量、Qdrant/OpenSearch/RRF/Reranker 延迟、Collection、索引版本和降级原因。

## 5. 成本目录

`data/config/model_pricing.yaml` 保存经过人工审核的价格版本。项目默认不填真实价格，避免过期价格造成错误成本结论。

示例：

```yaml
version: reviewed-2026-01
currency: CNY
models:
  qwen:qwen-plus:
    input_price_per_1k_tokens: 0.0
    output_price_per_1k_tokens: 0.0
```

本地 BGE-M3 没有按调用计费，但仍记录调用次数、文本数量、字符数、延迟和模型版本。

## 6. 查询 API

admin/engineer 可访问：

- `GET /api/v1/observability/requests/{request_id}`；
- `GET /api/v1/observability/analytics/overview`；
- `GET /api/v1/observability/analytics/timeseries`；
- `GET /api/v1/observability/analytics/models`；
- `GET /api/v1/observability/analytics/intents`；
- `GET /api/v1/observability/analytics/retrieval`。

## 7. 部署

```powershell
docker compose `
  -f docker-compose.yml `
  -f docker-compose.observability.yml `
  up -d
```

检查：

```powershell
docker compose exec api python -m scripts.test_observability
python -m scripts.test_observability_stack
python -m scripts.test_metrics
python -m scripts.test_usage_analytics
```

## 8. 告警建议

- graph-chat 5xx 错误率；
- P95/P99 总延迟和节点延迟；
- OpenSearch vector-only 降级率；
- Reranker 降级率；
- memory_degraded 比例；
- Embedding 维度错误或模型加载失败；
- Usage 写入失败/队列丢弃；
- Qdrant/OpenSearch 索引数量不一致；
- 文档 failed 状态积压。

## 9. 数据清理

```powershell
python -m scripts.cleanup_observability_data
```

清理前必须确认保留天数和数据库环境。指标、日志、Trace 和 PostgreSQL 明细应分别配置生命周期。
