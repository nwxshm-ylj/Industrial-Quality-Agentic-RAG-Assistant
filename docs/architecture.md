# System Architecture

## 1. Architecture goals

Industrial Quality Agentic RAG Assistant v1.0 is designed around five concerns:

1. Route different industrial questions to the correct tool or retrieval path.
2. Keep answers traceable to documents, rules, cases, or structured data.
3. Manage enterprise documents without rebuilding unrelated indexes.
4. Enforce authentication and authorization at the API boundary and high-risk tool boundary.
5. Capture request traces, audit events, user feedback, and evaluation metrics.

The system is a reference architecture rather than a production safety controller. Human review remains required for manufacturing decisions.

## 2. System context

~~~mermaid
flowchart LR
    Operator[Line Operator]
    Engineer[Quality Engineer]
    Admin[System Administrator]
    UI[Streamlit Web UI]
    API[FastAPI]
    LLM[OpenAI-compatible LLM]
    PG[(PostgreSQL)]
    QD[(Qdrant)]
    FS[(Mounted data directory)]

    Operator --> UI
    Engineer --> UI
    Admin --> UI
    UI --> API
    API --> LLM
    API --> PG
    API --> QD
    API --> FS
~~~

## 3. Container and module view

~~~mermaid
flowchart TB
    subgraph Client
        Browser[Browser]
        Streamlit[Streamlit]
    end

    subgraph Application
        FastAPI[FastAPI Routers]
        Auth[JWT + RBAC Dependencies]
        Graph[LangGraph Workflow]
        DocService[Document Service]
        FeedbackService[Feedback Service]
        EvalService[Evaluation Service]
        AuditService[Audit Service]
        Logger[JSON Logger]
    end

    subgraph AgentNodes
        Memory[Load Memory]
        Intent[Intent Router]
        Rewrite[Query Rewriter]
        Retrieve[Hybrid Retriever]
        Judge[Evidence Judge]
        Rule[Rule Tool]
        SQL[SQL Tool]
        Case[Case Retriever]
        Generate[Answer Generator]
        Save[Save Memory]
    end

    subgraph Data
        PostgreSQL[(PostgreSQL)]
        Qdrant[(Qdrant)]
        OpenSearch[(OpenSearch)]
        Uploads[(data/uploads)]
        Rules[(YAML Rules)]
    end

    Browser --> Streamlit --> FastAPI
    FastAPI --> Auth
    FastAPI --> Graph
    FastAPI --> DocService
    FastAPI --> FeedbackService
    FastAPI --> EvalService
    FastAPI --> AuditService
    FastAPI --> Logger

    Graph --> Memory --> Intent
    Intent --> Rewrite --> Retrieve --> Judge --> Generate --> Save
    Intent --> Rule --> Generate
    Intent --> SQL --> Generate
    Intent --> Case --> Generate

    Memory --> PostgreSQL
    Save --> PostgreSQL
    SQL --> PostgreSQL
    Case --> PostgreSQL
    DocService --> PostgreSQL
    DocService --> Qdrant
    DocService --> OpenSearch
    DocService --> Uploads
    Retrieve --> Qdrant
    Retrieve --> OpenSearch
    Rule --> Rules
    FeedbackService --> PostgreSQL
    EvalService --> Graph
    EvalService --> PostgreSQL
    AuditService --> PostgreSQL
~~~

## 4. LangGraph request flow

The workflow itself remains deliberately explicit. State carries the original question and all intermediate evidence.

~~~mermaid
flowchart TD
    Start([START]) --> Load[load_memory]
    Load --> Intent[intent_router]

    Intent -->|general| Generate[generate]
    Intent -->|rule_query| Rule[rule_tool]
    Intent -->|sql_analysis| SQL[sql_tool]
    Intent -->|case_search| Case[case_retriever]
    Intent -->|doc_qa or fault_diagnosis| Rewrite[query_rewriter]

    Rule -->|hit| Generate
    Rule -->|miss| Rewrite
    SQL --> Generate
    Case --> Generate

    Rewrite --> Retrieve[retrieve]
    Retrieve --> Judge[evidence_judge]
    Judge -->|enough| Generate
    Judge -->|retry allowed| Rewrite
    Judge -->|retry exhausted| Generate

    Generate --> Save[save_memory]
    Save --> End([END])
~~~

Important state fields:

| Category | Fields |
|---|---|
| Request | question, top_k, request_id, session_id, user |
| Memory | memory_messages |
| Routing | intent, rewritten_query |
| Evidence | contexts, citations, evidence_score, evidence_enough, retry_count |
| Tools | rule_result, sql_result, case_result |
| Output | answer |

## 5. Retrieval architecture

Hybrid retrieval combines complementary signals:

- Vector search captures semantic similarity and paraphrases.
- OpenSearch keyword retrieval captures model codes, alarm codes, part numbers, abbreviations, and exact industrial terminology.
- Reciprocal Rank Fusion combines vector and keyword rankings without assuming comparable raw score scales.
- Optional CrossEncoder reranking improves final ordering at a higher latency and memory cost.
- Evidence Judge prevents weak retrieval from being treated as strong evidence and can trigger one rewrite/retry.

The online path uses Qwen document/query embeddings, a versioned Qdrant collection queried through a stable alias, an OpenSearch keyword index, and RRF with a default k of 60. If OpenSearch is unavailable, retrieval may degrade to vector-only and reports that state in response metadata.

## 6. Knowledge ingestion flow

~~~mermaid
sequenceDiagram
    participant U as Admin or Engineer
    participant API as Documents API
    participant DS as DocumentService
    participant PG as PostgreSQL
    participant QD as Qdrant
    participant OS as OpenSearch

    U->>API: Upload file + doc_type + version
    API->>DS: file bytes
    DS->>DS: sanitize name + SHA-256
    DS->>PG: create uploaded metadata
    DS->>DS: parse and split
    DS->>PG: write document_chunks
    DS->>QD: write staging document points
    DS->>OS: bulk write staging keyword documents
    DS->>QD: promote operation to indexed
    DS->>OS: promote operation to indexed
    DS->>PG: status = indexed
    API-->>U: document metadata
~~~

Supported formats are Markdown, text, PDF, and DOCX. Legacy data/raw_docs ingestion remains available for initial demo collection creation.

## 7. Security model

Authentication and authorization are layered:

- Passwords are stored as salted PBKDF2-SHA256 hashes.
- Login creates a signed JWT containing username and role.
- FastAPI dependencies validate the Bearer token and active user.
- Route-level RBAC protects document, feedback, evaluation, and user APIs.
- SQL Tool performs an additional role check before database access.
- Permission denials are logged and audited.

Roles:

- admin: user management and all knowledge-base operations.
- engineer: chat, SQL analysis, document upload, feedback analytics, evaluation.
- viewer: chat, document viewing, and feedback submission only.

UI role checks improve usability. They are not security boundaries; API checks remain authoritative.

## 8. Data model ownership

| Store | Main data |
|---|---|
| PostgreSQL | users, audit logs, conversations, documents, chunks, feedback, evaluation runs/items, quality records |
| Qdrant | Qwen document vectors and versioned payload metadata; runtime queries use a stable alias |
| OpenSearch | Online keyword documents used by Hybrid Search |
| data/processed/chunks.json | Legacy Demo BM25 data only; not an online runtime dependency |
| data/uploads | Uploaded source files |
| data/rules | Rule Tool YAML |
| data/eval | Evaluation questions and JSON reports |

## 9. Observability and quality loop

~~~mermaid
flowchart LR
    Client --> API[FastAPI request context]
    API --> Graph[LangGraph spans]
    Graph --> Dependencies[LLM / Embedding / PostgreSQL / Qdrant / OpenSearch]
    API --> JSON[Structured JSON logs]
    Graph --> Usage[Request usage context]
    API --> OTEL[OpenTelemetry Collector]
    OTEL --> Tempo
    API --> Prometheus
    JSON --> Alloy --> Loki
    Usage --> UsageDB[(PostgreSQL usage facts)]
    Tempo --> Grafana
    Prometheus --> Grafana
    Loki --> Grafana
    UsageDB --> Grafana
    Feedback --> UsageDB
    Evaluation --> UsageDB
~~~

The existing `request_id` remains the business correlation identifier. A standard
`trace_id` and per-operation `span_id` add distributed trace navigation without
changing the graph-chat contract. `session_id` correlates conversational history.

Operational signals are separated by purpose:

- OpenTelemetry spans cover HTTP, graph nodes, model calls, embeddings, retrieval,
  and database operations.
- Prometheus metrics expose low-cardinality request, node, model, and retrieval
  counters and latency histograms.
- JSON logs include request, trace, service, environment, status, and error fields;
  sensitive content is filtered before serialization.
- `rag_request_runs`, `ai_usage_events`, and `retrieval_events` store request-level
  usage facts, token counts, calculated cost, retrieval mode, and dependency timing.
- Grafana dashboards combine Prometheus, Tempo, Loki, PostgreSQL feedback, and
  evaluation data.

Question text, answers, prompts, document content, API keys, JWTs, and passwords are
not stored in metrics or trace attributes. Cost is calculated only when the reviewed
pricing catalog contains the provider/model entry; missing prices remain unpriced.

## 10. Current boundaries

- `scripts/ingest_docs.py` and `chunks.json` remain Legacy Demo assets and are isolated from the online Qwen/OpenSearch path.
- Full online migration is allowed only before the stable Qdrant alias targets the new collection; later repairs use per-document reindex.
- Evaluation runs synchronously in v1.0.
- PostgreSQL initialization is demo-oriented and recreates three sample business tables.
- SQL validation is intentionally restricted but should still use a dedicated read-only production account.
- Multi-tenancy, document ACL, queue workers, production trace tail sampling, and object storage are roadmap items.
