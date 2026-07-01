from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "industrial_docs"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    llm_model: str = "qwen-plus"
    llm_api_key: str
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    database_url: str = "postgresql+psycopg2://rag_user:rag_password@localhost:5432/industrial_rag"

    reranker_model: str = "BAAI/bge-reranker-base"
    use_reranker: bool = True

    jwt_secret_key: str = "dev_secret_key_change_me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    class Config:
        env_file = ".env"


settings = Settings()