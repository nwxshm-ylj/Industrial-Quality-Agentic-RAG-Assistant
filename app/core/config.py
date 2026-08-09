from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    telemetry_enabled: bool = True
    metrics_enabled: bool = True
    usage_analytics_enabled: bool = True
    otel_service_name: str = "industrial-quality-rag-api"
    otel_service_version: str = "1.0.0"
    otel_exporter_otlp_endpoint: str | None = None
    otel_trace_sample_ratio: float = 1.0
    otel_export_timeout_seconds: float = 5.0
    telemetry_capture_content: bool = False
    model_pricing_path: str = "data/config/model_pricing.yaml"
    usage_retention_days: int = 90
    usage_background_workers: int = 4
    usage_background_max_pending: int = 1000

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "industrial_docs_qwen_1024_v1"
    qdrant_collection_alias: str = "industrial_docs_active"
    legacy_qdrant_collection: str = "industrial_docs"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_provider: str = "qwen"
    qwen_embedding_model: str = "text-embedding-v4"
    qwen_embedding_dimension: int = 1024
    qwen_embedding_api_key: str | None = None
    qwen_embedding_base_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
        "text-embedding/text-embedding"
    )
    qwen_embedding_batch_size: int = 10
    embedding_index_version: str = "qwen-1024-v1"

    multimodal_enabled: bool = False
    multimodal_embedding_provider: str = "qwen"
    qwen_multimodal_embedding_model: str = "qwen3-vl-embedding"
    qwen_multimodal_embedding_dimension: int = 1024
    qwen_multimodal_embedding_api_key: str | None = None
    qwen_multimodal_embedding_base_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
        "multimodal-embedding/multimodal-embedding"
    )
    multimodal_embedding_index_version: str = "qwen3vl-1024-v1"
    qdrant_multimodal_collection: str = (
        "industrial_multimodal_qwen3vl_1024_v1"
    )
    qdrant_multimodal_collection_alias: str = "industrial_multimodal_active"
    multimodal_degraded_mode: str = "text_only"
    dots_ocr_url: str | None = None
    dots_ocr_timeout_seconds: float = 120.0

    document_chunk_size: int = 700
    document_chunk_overlap: int = 100
    document_chunk_strategy: str = "layout_token_v2"
    document_chunk_target_tokens: int = 384
    document_chunk_max_tokens: int = 512
    document_chunk_overlap_tokens: int = 48
    document_parser_backend: str = "auto"
    document_parser_fallback: str = "native"
    deepdoc_enabled: bool = False
    deepdoc_runtime_factory: str | None = None
    deepdoc_model_dir: str = "data/models/deepdoc"
    deepdoc_require_model_files: bool = True
    deepdoc_zoomin: int = 3
    deepdoc_max_pages: int = 2000

    opensearch_url: str = "http://localhost:9200"
    opensearch_index_prefix: str = "industrial_docs"
    opensearch_username: str | None = None
    opensearch_password: str | None = None
    opensearch_verify_certs: bool = True
    opensearch_connect_timeout: float = 5.0
    opensearch_read_timeout: float = 10.0
    opensearch_pool_maxsize: int = 20
    opensearch_max_retries: int = 3
    opensearch_retry_on_timeout: bool = True
    keyword_search_backend: str = "opensearch"
    keyword_index_version: str = "v1"
    hybrid_degraded_mode: str = "vector_only"
    retrieval_fusion_strategy: str = "rrf"
    retrieval_rrf_k: int = 60
    retrieval_vector_weight: float = 0.65
    retrieval_keyword_weight: float = 0.35
    reranker_fail_open: bool = True

    llm_model: str = "qwen-plus"
    llm_provider: str = "qwen"
    llm_api_key: str
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    prompt_catalog_path: str = "prompts/catalog"
    prompt_release_path: str = "prompts/releases/stable.yaml"
    prompt_validate_on_startup: bool = True
    prompt_expose_version_in_response: bool = True

    ragas_enabled: bool = False
    ragas_version: str = "0.4.3"
    ragas_judge_model: str = "qwen-plus"
    ragas_embedding_model: str = "text-embedding-v4"
    ragas_dataset_path: str = "data/eval/ragas_eval_questions.json"

    database_url: str = "postgresql+psycopg2://rag_user:rag_password@localhost:5432/industrial_rag"

    layered_memory_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    redis_connect_timeout_seconds: float = 2.0
    redis_read_timeout_seconds: float = 2.0
    memory_redis_key_prefix: str = "industrial_rag:memory"
    memory_short_term_ttl_seconds: int = 86400
    memory_short_term_max_messages: int = 20
    memory_summary_trigger_messages: int = 12
    memory_recent_limit: int = 6
    memory_long_term_limit: int = 4
    memory_semantic_score_threshold: float = 0.45
    memory_keyword_min_score: float = 0.0
    memory_qdrant_collection: str = "industrial_memory_qwen_1024_v1"
    memory_index_version: str = "v1"
    memory_background_workers: int = 2
    memory_background_max_pending: int = 100

    knowledge_graph_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "rag_graph_password"
    neo4j_database: str = "neo4j"
    neo4j_connection_timeout_seconds: float = 5.0
    neo4j_max_connection_pool_size: int = 20
    knowledge_graph_result_limit: int = 5

    reranker_model: str = "BAAI/bge-reranker-base"
    use_reranker: bool = True

    jwt_secret_key: str = "dev_secret_key_change_me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

settings = Settings()
