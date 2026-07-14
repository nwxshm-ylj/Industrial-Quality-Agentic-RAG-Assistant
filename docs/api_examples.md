# API Examples

Base URL:

~~~bash
export API_BASE=http://localhost:8000
~~~

PowerShell equivalents can use $env:API_BASE and $env:TOKEN.

All enterprise APIs except login and health require a Bearer token. The legacy /api/v1/chat route is retained for compatibility; use authenticated /api/v1/graph-chat for demonstrations.

## 1. Login

~~~bash
curl -X POST "$API_BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
~~~

Response:

~~~json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "username": "admin",
    "role": "admin",
    "is_active": true
  }
}
~~~

Copy access_token:

~~~bash
export TOKEN="eyJ..."
~~~

## 2. Agentic graph-chat

First turn:

~~~bash
curl -X POST "$API_BASE/api/v1/graph-chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "轮毂识别异常可能是什么原因？",
    "top_k": 3,
    "session_id": "demo-session-001"
  }'
~~~

Follow-up using the same session_id:

~~~bash
curl -X POST "$API_BASE/api/v1/graph-chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "那优先排查哪个？",
    "top_k": 3,
    "session_id": "demo-session-001"
  }'
~~~

Representative response:

~~~json
{
  "question": "那优先排查哪个？",
  "answer": "...",
  "citations": [],
  "request_id": "c2ec3b4e-...",
  "session_id": "demo-session-001",
  "memory_messages": [
    {
      "role": "user",
      "content": "轮毂识别异常可能是什么原因？"
    }
  ],
  "metadata": {
    "intent": "fault_diagnosis",
    "evidence_score": 0.78,
    "evidence_enough": true,
    "retry_count": 0,
    "total_latency_ms": 1250.4
  },
  "intent": "fault_diagnosis",
  "evidence_score": 0.78,
  "evidence_enough": true,
  "retry_count": 0
}
~~~

Save request_id, answer, citations, intent, and metadata if the response will be submitted as feedback.

## 3. Upload and index a document

Supported extensions: md, txt, pdf, docx.

~~~bash
curl -X POST "$API_BASE/api/v1/documents/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./demo_quality_sop.txt" \
  -F "doc_type=SOP" \
  -F "version=v1"
~~~

Only admin and engineer can upload.

Example response:

~~~json
{
  "doc_id": "7fc...",
  "filename": "demo_quality_sop.txt",
  "doc_type": "SOP",
  "version": "v1",
  "status": "indexed",
  "chunk_count": 2
}
~~~

## 4. List documents

~~~bash
curl "$API_BASE/api/v1/documents" \
  -H "Authorization: Bearer $TOKEN"
~~~

Filter by status:

~~~bash
curl "$API_BASE/api/v1/documents?status=indexed" \
  -H "Authorization: Bearer $TOKEN"
~~~

Get one document:

~~~bash
curl "$API_BASE/api/v1/documents/DOC_ID" \
  -H "Authorization: Bearer $TOKEN"
~~~

Admin-only maintenance:

~~~bash
curl -X POST "$API_BASE/api/v1/documents/DOC_ID/reindex" \
  -H "Authorization: Bearer $TOKEN"

curl -X DELETE "$API_BASE/api/v1/documents/DOC_ID" \
  -H "Authorization: Bearer $TOKEN"
~~~

## 5. Submit answer feedback

Use fields from the graph-chat response:

~~~bash
curl -X POST "$API_BASE/api/v1/feedback" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "c2ec3b4e-...",
    "session_id": "demo-session-001",
    "question": "那优先排查哪个？",
    "answer": "优先检查相机曝光、安装位置和标定状态。",
    "rating": "positive",
    "comment": "排查顺序清楚，引用准确",
    "intent": "fault_diagnosis",
    "citations": [
      {
        "source": "wheel_fmea.md",
        "doc_type": "FMEA"
      }
    ],
    "metadata": {
      "evidence_score": 0.78,
      "total_latency_ms": 1250.4
    }
  }'
~~~

Allowed ratings are positive, negative, and neutral. All three roles can submit feedback.

## 6. Feedback statistics

admin and engineer only:

~~~bash
curl "$API_BASE/api/v1/feedback/stats" \
  -H "Authorization: Bearer $TOKEN"
~~~

List negative feedback:

~~~bash
curl "$API_BASE/api/v1/feedback?rating=negative&limit=50" \
  -H "Authorization: Bearer $TOKEN"
~~~

## 7. Run RAG evaluation

admin and engineer only. v1.0 runs synchronously.

~~~bash
curl -X POST "$API_BASE/api/v1/evaluation/run" \
  -H "Authorization: Bearer $TOKEN"
~~~

List runs:

~~~bash
curl "$API_BASE/api/v1/evaluation/runs?limit=20" \
  -H "Authorization: Bearer $TOKEN"
~~~

Get one run with item details:

~~~bash
curl "$API_BASE/api/v1/evaluation/runs/RUN_ID" \
  -H "Authorization: Bearer $TOKEN"
~~~

### Retrieval-only evaluation

This path evaluates ranked Qdrant + OpenSearch retrieval without invoking the
answer-generating LLM. It still calls the configured query EmbeddingProvider.

~~~bash
curl -X POST "$API_BASE/api/v1/evaluation/retrieval/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "top_k": 5,
    "k_values": [1, 3, 5]
  }'

curl "$API_BASE/api/v1/evaluation/retrieval/runs?limit=20" \
  -H "Authorization: Bearer $TOKEN"

curl "$API_BASE/api/v1/evaluation/retrieval/runs/RETRIEVAL_RUN_ID" \
  -H "Authorization: Bearer $TOKEN"
~~~

The response includes Precision@K, Recall@K, HitRate@K, MRR@K, nDCG@K,
P50/P95/P99 retrieval latency, backend latency breakdown, degraded status, and
ranked result identifiers. Document text is not copied into the report.

## 8. User administration

admin only:

~~~bash
curl -X POST "$API_BASE/api/v1/auth/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "quality_engineer",
    "password": "replace_me",
    "role": "engineer"
  }'

curl "$API_BASE/api/v1/auth/users" \
  -H "Authorization: Bearer $TOKEN"
~~~

## 9. Error behavior

| Status | Meaning |
|---|---|
| 400 | Invalid input or unsupported document |
| 401 | Missing, invalid, or expired token |
| 403 | Authenticated role lacks permission |
| 404 | Document or evaluation run not found |
| 409 | Duplicate user or conflicting resource |
| 422 | Pydantic request validation failed |
| 500 | Internal operation failed |
| 503 | Evaluation failed because a required model/service was unavailable |

## Observability and usage analytics

The existing Bearer token is required for the following admin/engineer endpoints.

~~~bash
curl -s "$API_BASE/api/v1/observability/analytics/overview" \
  -H "Authorization: Bearer $TOKEN"

curl -s "$API_BASE/api/v1/observability/analytics/timeseries?granularity=day" \
  -H "Authorization: Bearer $TOKEN"

curl -s "$API_BASE/api/v1/observability/analytics/models" \
  -H "Authorization: Bearer $TOKEN"

curl -s "$API_BASE/api/v1/observability/analytics/retrieval" \
  -H "Authorization: Bearer $TOKEN"
~~~

Inspect one request by the `request_id` returned from graph-chat:

~~~bash
curl -s "$API_BASE/api/v1/observability/requests/c2ec3b4e-..." \
  -H "Authorization: Bearer $TOKEN"
~~~

Operational endpoints used by the container platform and Prometheus do not invoke a
paid model API:

~~~bash
curl -s "$API_BASE/health/live"
curl -s "$API_BASE/health/ready"
curl -s "$API_BASE/metrics"
~~~

The API also returns X-Request-ID for support and log correlation.
