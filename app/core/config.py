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

    llm_model: str = "qwen-plus"
    llm_provider: str = "qwen"
    llm_api_key: str
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    prompt_catalog_path: str = "prompts/catalog"
    prompt_release_path: str = "prompts/releases/stable.yaml"
    prompt_validate_on_startup: bool = True
    prompt_expose_version_in_response: bool = True

    database_url: str = "postgresql+psycopg2://rag_user:rag_password@localhost:5432/industrial_rag"

    reranker_model: str = "BAAI/bge-reranker-base"
    use_reranker: bool = True

    jwt_secret_key: str = "dev_secret_key_change_me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

settings = Settings()
