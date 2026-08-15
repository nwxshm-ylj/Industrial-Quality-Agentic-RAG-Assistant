from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalFilterRequest(BaseModel):
    doc_ids: list[str] | None = Field(default=None, max_length=50)
    doc_types: list[str] | None = Field(default=None, max_length=50)
    versions: list[str] | None = Field(default=None, max_length=50)
    sources: list[str] | None = Field(default=None, max_length=50)


class MultimodalQueryRequest(BaseModel):
    images: list[str] | None = Field(default=None, max_length=5)
    video: str | None = None

    @model_validator(mode="after")
    def validate_media(self):
        images = self.images or []
        if not images and not self.video:
            raise ValueError("multimodal_query requires images or video")
        for image in images:
            if len(image) > 14 * 1024 * 1024:
                raise ValueError("multimodal image input is too large")
            if not image.startswith(("http://", "https://", "data:image/")):
                raise ValueError(
                    "multimodal image must be HTTP(S) URL or data:image URI"
                )
        if self.video and not self.video.startswith(("http://", "https://")):
            raise ValueError("multimodal video must be an HTTP(S) URL")
        return self


class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    top_k: int = Field(default=5, ge=1, le=10)
    retrieval_filters: RetrievalFilterRequest | None = Field(
        default=None,
        description="Optional metadata filters applied inside retrieval backends",
    )
    multimodal_query: MultimodalQueryRequest | None = None
    session_id: str = Field(default="default", description="会话ID")


class Citation(BaseModel):
    doc_id: str | None = None
    source: str | None = None
    doc_type: str | None = None
    chunk_id: str | None = None
    asset_id: str | None = None
    asset_path: str | None = None
    preview_url: str | None = None
    page_number: int | None = None
    modality: str | None = None
    version: str | None = None
    score: float | None = None
    retrieval_source: str | None = None
    vector_score: float | None = None
    bm25_score: float | None = None
    keyword_score: float | None = None
    hybrid_score: float | None = None
    rrf_score: float | None = None
    weighted_score: float | None = None
    rerank_score: float | None = None
    final_score_type: str | None = None
    cross_modal_rrf_score: float | None = None
    text_hybrid_score: float | None = None
    multimodal_score: float | None = None
    traceability_role: str | None = None
    quality_entities: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]

    request_id: str | None = None
    session_id: str | None = None
    memory_messages: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None

    intent: str | None = None
    rewritten_query: str | None = None
    evidence_score: float | None = None
    evidence_enough: bool | None = None
    retry_count: int | None = None

    rule_result: dict[str, Any] | None = None
    sql_result: dict[str, Any] | None = None
    case_result: dict[str, Any] | None = None
    contexts: list[dict[str, Any]] | None = None
