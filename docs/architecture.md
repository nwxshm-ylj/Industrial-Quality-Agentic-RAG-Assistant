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
        Chunks[(chunks.json)]
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
    DocService --> Chunks
    DocService --> Uploads
    Retrieve --> Qdrant
    Retrieve --> Chunks
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
- BM25 captures model codes, alarm codes, part numbers, abbreviations, and exact industrial terminology.
- Optional CrossEncoder reranking improves final ordering at a higher latency and memory cost.
- Evidence Judge prevents weak retrieval from being treated as strong evidence and can trigger one rewrite/retry.

The current defaults use vector weight 0.65 and BM25 weight 0.35. These values are configuration/implementation defaults, not universal optimums; production tuning should use a versioned evaluation set.

## 6. Knowledge ingestion flow

~~~mermaid
sequenceDiagram
    participant U as Admin or Engineer
    participant API as Documents API
    participant DS as DocumentService
    participant PG as PostgreSQL
    participant QD as Qdrant
    participant BM as chunks.json

    U->>API: Upload file + doc_type + version
    API->>DS: file bytes
    DS->>DS: sanitize name + SHA-256
    DS->>PG: create uploaded metadata
    DS->>DS: parse and split
    DS->>PG: write document_chunks
    DS->>QD: add stable document points
    DS->>BM: refresh enterprise chunks
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
| Qdrant | Document vectors and payload metadata |
| data/processed/chunks.json | BM25-compatible chunks |
| data/uploads | Uploaded source files |
| data/rules | Rule Tool YAML |
| data/eval | Evaluation questions and JSON reports |

## 9. Observability and quality loop

~~~mermaid
flowchart LR
    Question --> Answer
    Answer --> Feedback
    Answer --> Logs
    Answer --> Audit
    Feedback --> Stats
    EvalSet[Evaluation Set] --> EvalRun[Evaluation Run]
    EvalRun --> Metrics
    Stats --> Improve[Prompt / Data / Retrieval Improvement]
    Metrics --> Improve
    Improve --> Question
~~~

request_id correlates API responses, node logs, feedback, and audit records. session_id correlates conversational history. Node latency and total latency make slow stages visible.

## 10. Current boundaries

- BM25 is file-backed and loaded into process memory; document updates require API restart for BM25 refresh.
- Evaluation runs synchronously in v1.0.
- PostgreSQL initialization is demo-oriented and recreates three sample business tables.
- SQL validation is intentionally restricted but should still use a dedicated read-only production account.
- Multi-tenancy, document ACL, queue workers, distributed tracing, and object storage are roadmap items.
