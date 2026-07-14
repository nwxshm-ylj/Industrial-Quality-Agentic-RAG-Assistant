# Enterprise Observability and Usage Analytics

## Signal model

The project keeps four signal types separate while correlating them with
`request_id` and `trace_id`:

| Signal | Backend | Purpose |
|---|---|---|
| Traces | OpenTelemetry Collector and Tempo | Request and dependency call tree |
| Metrics | Prometheus | Rates, errors, latency, degradation, and model usage |
| Logs | JSON stdout, Alloy, and Loki | Detailed searchable events and errors |
| Usage facts | PostgreSQL | Tokens, calculated cost, intent, retrieval, and quality analysis |

Telemetry backend failure does not fail graph-chat. PostgreSQL usage persistence is
best effort in a separate transaction and emits `usage_persist_failed` plus a
Prometheus counter if it cannot write. HTTP persistence runs in a bounded background
task pool. When `USAGE_BACKGROUND_MAX_PENDING` is reached, new usage facts are
dropped with `usage_persist_queue_full` instead of exhausting application memory.

## Correlation identifiers

- `request_id`: existing API and business identifier.
- `trace_id`: OpenTelemetry trace identifier.
- `span_id`: individual graph node or dependency operation.
- `session_id`: conversation memory identifier.

Do not use request, session, or user identifiers as Prometheus labels. They are
available in traces, logs, audit records, and PostgreSQL where high-cardinality
queries are appropriate.

## Usage tables

### rag_request_runs

One row per graph-chat request and per API request that consumes a model or embedding.
It contains route, latency, intent, evidence, retrieval mode, degradation state,
aggregate tokens, calculated cost, and request status. This includes document upload
and reindex embedding consumption.

### ai_usage_events

One row per LLM or embedding call. Document and query embeddings are recorded as
separate operations. Provider-reported token counts are marked with
`measurement_source=provider`; missing usage is kept as unavailable rather than
silently estimated.

### retrieval_events

One row per document retrieval. It contains vector/keyword/fused counts, Qdrant and
OpenSearch latency, RRF latency, reranker latency, and degraded mode.

## Cost catalog

`data/config/model_pricing.yaml` intentionally starts without prices. Add reviewed
provider prices and a version before using cost totals for budgeting. Each event
stores the pricing version and amount calculated at event time so later catalog
changes do not rewrite history.

Example structure (replace the example rates with reviewed current prices):

~~~yaml
version: reviewed-2026-01
currency: CNY
models:
  qwen:qwen-plus:
    input_price_per_1k_tokens: 0.0
    output_price_per_1k_tokens: 0.0
  qwen:text-embedding-v4:
    embedding_price_per_1k_tokens: 0.0
~~~

Never commit provider credentials to the pricing file or telemetry configuration.

## APIs

The following endpoints use the existing admin/engineer RBAC dependency:

- `GET /api/v1/observability/requests/{request_id}`
- `GET /api/v1/observability/analytics/overview`
- `GET /api/v1/observability/analytics/timeseries`
- `GET /api/v1/observability/analytics/models`
- `GET /api/v1/observability/analytics/intents`
- `GET /api/v1/observability/analytics/retrieval`

Analytics endpoints accept optional ISO-8601 `start_at` and `end_at` parameters and
default to the most recent seven days. Timeseries additionally accepts
`granularity=hour|day`.

Retrieval-only evaluation publishes low-cardinality latest-run metrics:

- `industrial_rag_retrieval_evaluation_runs_total`
- `industrial_rag_retrieval_evaluation_score{metric,k}`
- `industrial_rag_retrieval_evaluation_latency_ms{quantile}`

The Grafana `Industrial RAG - Retrieval and Quality` dashboard displays the latest
Recall/MRR/HitRate/nDCG and P50/P95/P99 values. Versioned historical reports remain
in `data/eval/retrieval_eval_report_<run_id>.json`.

## Privacy rules

The telemetry filter redacts secrets based on field names and masks Bearer tokens,
URL passwords, and common query-string secrets. Prompt, question, answer, document
content, passwords, JWTs, and API keys must not be added as metric labels or span
attributes.

The existing feedback table intentionally stores question and answer content for the
quality workflow. Access and retention for that business dataset should be governed
separately from operational telemetry.

## Retention

`USAGE_RETENTION_DAYS` defaults to 90. Run the cleanup command from a controlled
scheduler or maintenance job:

~~~bash
python -m scripts.cleanup_observability_data --days 90
~~~

The cleanup is scoped only to `rag_request_runs`, `ai_usage_events`, and
`retrieval_events`; it does not delete audit, feedback, evaluation, conversation, or
knowledge-base data.

## Development validation

Offline checks:

~~~bash
python -m scripts.test_telemetry_context
python -m scripts.test_model_usage_mock
python -m scripts.test_metrics
python -m scripts.test_observability_stack
~~~

PostgreSQL integration check:

~~~bash
python -m scripts.test_usage_analytics
~~~

Do not run `scripts.init_sql_data` against an unknown or production database; it also
recreates the three demo business tables.
