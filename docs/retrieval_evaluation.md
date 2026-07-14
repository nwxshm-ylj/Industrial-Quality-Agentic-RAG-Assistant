# Retrieval Evaluation

## Purpose

The retrieval evaluator measures the online search layer independently from intent
routing, LangGraph orchestration, answer generation, and conversation memory. This
separates retrieval quality and latency regressions from LLM answer variability.

Runtime path under evaluation:

~~~text
question
  -> Qwen query embedding
  -> Qdrant vector search through industrial_docs_active
  -> OpenSearch keyword search
  -> Reciprocal Rank Fusion
  -> optional reranker
  -> ranked contexts
~~~

The evaluator never reads `chunks.json` and never invokes the answer-generating LLM.
Online runs do call the configured query EmbeddingProvider and can incur embedding
API usage.

## Dataset

The default benchmark is `data/eval/retrieval_eval_questions.json`.

~~~json
{
  "id": "RET001",
  "question": "轮毂识别异常可能是什么原因？",
  "relevance_field": "source",
  "relevant_ids": ["ai_vision_fmea.md"]
}
~~~

Supported relevance fields are `source`, `doc_id`, and `chunk_id`. Multiple
`relevant_ids` are supported. Source matching normalizes path separators and compares
the filename case-insensitively. Rankings are deduplicated by the selected relevance
field so multiple chunks from one relevant document do not inflate document-level
metrics.

For a production benchmark, prefer stable canonical `doc_id` or `chunk_id` labels
reviewed by domain experts. Keep the dataset versioned with the index, embedding
model, and retrieval configuration being evaluated.

## Metrics

- `Precision@K`: relevant unique results in Top K divided by K.
- `Recall@K`: relevant unique results in Top K divided by all labeled relevant IDs.
- `HitRate@K`: fraction of questions with at least one relevant result in Top K.
- `MRR@K`: mean reciprocal rank of the first relevant result within Top K.
- `nDCG@K`: normalized discounted cumulative gain for binary relevance labels.
- Retrieval latency: min, average, P50, P95, P99, and max.
- Component latency: Qdrant, OpenSearch, RRF fusion, and reranker distributions.
- Degraded rate: queries that fell back from hybrid to vector-only retrieval.

Failed questions remain in the metric denominator with zero ranking scores. A run is
`completed`, `partial`, or `failed`; failures are not silently skipped.

## Commands

Offline deterministic tests, with `MockEmbeddingProvider` and no external API calls:

~~~bash
python -m scripts.test_retrieval_evaluation
python -m scripts.test_metrics
~~~

Online evaluation against Qdrant, OpenSearch, and the configured query embedding API:

~~~bash
python -m scripts.evaluate_retrieval --top-k 5 --k-values 1,3,5
~~~

Docker:

~~~bash
docker compose exec api python -m scripts.test_retrieval_evaluation
docker compose exec api python -m scripts.evaluate_retrieval --top-k 5 --k-values 1,3,5
~~~

Use `--max-questions 1` for a minimal integration smoke test. The CLI writes both a
versioned report and `data/eval/retrieval_eval_report.json` as the latest snapshot.

## API and RBAC

admin and engineer roles can use:

- `POST /api/v1/evaluation/retrieval/run`
- `GET /api/v1/evaluation/retrieval/runs`
- `GET /api/v1/evaluation/retrieval/runs/{run_id}`

viewer access is denied by the existing RBAC dependency. Run and view operations are
written to the existing audit log. The API does not accept an arbitrary dataset path;
it always uses the repository-controlled benchmark path.

## Reports and privacy

Reports include question text, expected identifiers, returned identifiers, ranks,
scores, retrieval source, quality metrics, and latency. Retrieved document body text
is intentionally omitted. Treat benchmark questions and identifiers as governed test
data and apply the same repository access controls used for other evaluation assets.

Prometheus exposes only low-cardinality metric name and K labels. It never labels
metrics with question text, run ID, document ID, username, or request ID.
