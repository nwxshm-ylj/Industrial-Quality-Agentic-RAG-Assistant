# Demo Script

This script provides a 15–20 minute end-to-end demonstration suitable for a project review, interview, or portfolio recording.

## 0. Preparation

Start the stack and initialize demo data:

~~~bash
docker compose up -d qdrant postgres
docker compose --profile tools run --rm init-sql
docker compose --profile tools run --rm ingest
docker compose up -d --build api streamlit
~~~

Open:

- Streamlit: http://localhost:30000
- Swagger: http://localhost:8000/docs
- Qdrant dashboard: http://localhost:6333/dashboard

Prepare a small document named demo_quality_sop.txt:

~~~text
轮毂识别异常排查 SOP
1. 优先检查相机曝光、镜头污染和安装位置。
2. 确认相机标定状态。
3. 核对车型、轮毂型号和 PR 配置。
4. 检查 MES 配置同步与网络上传状态。
~~~

Narration: “The demo covers the complete enterprise loop: identity, knowledge ingestion, Agentic RAG, tools, memory, feedback, evaluation, and audit.”

## 1. Admin login

1. Open Streamlit.
2. Enter admin / admin123.
3. Click login.
4. Point out the username and role in the sidebar.

Expected:

- Login succeeds.
- JWT is stored in Streamlit session_state.
- Subsequent API requests include Authorization: Bearer token.
- Login is recorded in operation_audit_logs.

Talking point: “UI state improves usability, but authorization is always enforced again by FastAPI dependencies.”

## 2. Upload an industrial document

1. Open Knowledge Base Management.
2. Select demo_quality_sop.txt.
3. Set doc_type to SOP and version to v1.
4. Upload and index.

Expected:

- Response status is indexed.
- A doc_id and chunk_count are displayed.
- Metadata and chunks are written to PostgreSQL.
- Vectors are written to Qdrant.
- chunks.json is synchronized for BM25.

Talking point: “The upload path uses filename sanitization, SHA-256 duplicate detection, stable point IDs, and status transitions.”

## 3. View the document list

1. Refresh the document list.
2. Locate the uploaded file.
3. Show doc_id, filename, doc_type, version, status, and chunk_count.

Optional:

- Explain that admin can delete and reindex.
- Explain that engineer can upload and view.
- Explain that viewer can only view.

## 4. Normal RAG question

Ask:

~~~text
轮毂识别异常可能是什么原因？
~~~

Show:

- Final answer.
- citations.
- contexts.
- intent and evidence score.
- request_id and total_latency_ms in raw JSON.

Expected intent: fault_diagnosis.

Talking point: “The system does not directly call the LLM. It routes, rewrites, retrieves, judges evidence, optionally retries, and only then generates.”

## 5. Multi-turn memory follow-up

Without changing the session, ask:

~~~text
那优先排查哪个？
~~~

Show memory_messages in raw JSON or explain that the same session_id is sent.

Expected:

- The system understands “那” as the previous wheel-recognition issue.
- Recent messages are loaded from PostgreSQL.
- Historical dialog helps resolve references but does not replace retrieved evidence.

## 6. Rule Tool query

Ask:

~~~text
PR001 对应什么轮毂配置？
~~~

Show the Rule Tool result and citation.

Expected intent: rule_query.

Talking point: “Deterministic rules are preferred over probabilistic document generation when a structured rule match exists.”

## 7. SQL Tool query

Ask as admin:

~~~text
最近一周 ZP8 工位误识别数量是多少？
~~~

Show:

- sql_analysis intent.
- generated or matched read-only SQL.
- row_count and rows.
- SQL Tool audit entry.

Security contrast:

- Login as viewer and ask the same question.
- Show the 403 response or permission message.

Talking point: “SQL permission is checked at the route/user layer and again before SQL Tool execution.”

## 8. Case Retriever query

Ask:

~~~text
历史上有没有类似的轮毂误识别案例？
~~~

Show case_result with station, phenomenon, root cause, and action.

Expected intent: case_search.

Talking point: “Historical cases are relational business data, so the system routes to PostgreSQL instead of forcing every source through the vector store.”

## 9. Submit answer feedback

Under the latest answer:

1. Select 👍 有用, 👎 无用, or 😐 一般.
2. Enter a note such as “引用准确，排查顺序清楚”.
3. Submit.

Expected:

- The feedback API stores request_id, session_id, question, answer, rating, intent, citations, and metadata.
- A feedback_create audit record and structured log are produced.

Talking point: “request_id connects the user’s judgment back to the exact response and runtime trace.”

## 10. View the RAG Evaluation dashboard

As admin or engineer:

1. Open RAG Evaluation.
2. Show positive, negative, and neutral counts.
3. Filter recent feedback by rating.
4. Show intent distribution.
5. Click Run Evaluation.
6. Show the latest run metrics.

Metrics:

- intent_accuracy
- source_hit_rate
- answer_keyword_hit_rate
- memory_followup_success_rate
- avg_latency_ms

Note: the evaluation is synchronous in v1.0 and may take several minutes.

## 11. View audit logs

There is no audit-log management API in v1.0. Query PostgreSQL directly for the demonstration:

~~~bash
docker compose exec postgres psql \
  -U rag_user \
  -d industrial_rag \
  -c "SELECT created_at, request_id, username, role, action, resource_type, status FROM operation_audit_logs ORDER BY id DESC LIMIT 30;"
~~~

Point out:

- login_success / login_failed
- graph_chat
- sql_tool_execute
- document_upload
- feedback_create
- rag_evaluation_run
- permission_denied

Talking point: “Audit write failures are isolated from the main business request, but still emit error logs.”

## 12. Closing summary

Use this 30-second close:

> “This project demonstrates more than a RAG chatbot. It combines explicit LangGraph routing, hybrid retrieval, deterministic tools, session memory, enterprise knowledge management, JWT/RBAC, request-level observability, audit logs, user feedback, and measurable evaluation. The architecture keeps each concern independently testable and provides a clear path toward multi-tenancy, asynchronous ingestion, distributed tracing, and production governance.”

## Demo fallback plan

If the LLM provider is unavailable:

- Demonstrate login, document list, RBAC, feedback statistics, and audit logs.
- Use saved evaluation reports in data/eval.
- Show Swagger request/response schemas.
- Explain that embedding and LLM connectivity are external prerequisites.

If the embedding model is still downloading:

- Show container logs.
- Explain the hf_cache volume.
- Continue with authentication and PostgreSQL-backed features.
