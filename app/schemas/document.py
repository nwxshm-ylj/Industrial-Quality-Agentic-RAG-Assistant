from datetime import datetime

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    original_filename: str | None = None
    doc_type: str | None = None
    file_ext: str | None = None
    version: str
    status: str
    chunk_count: int
    failed_stage: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int


class DocumentUploadResponse(DocumentInfo):
    pass


class DocumentDeleteResponse(BaseModel):
    doc_id: str
    status: str
    message: str


class DocumentReindexResponse(BaseModel):
    doc_id: str
    status: str
    chunk_count: int
    message: str
