from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogItem(BaseModel):
    id: int
    request_id: str | None = None
    session_id: str | None = None
    username: str | None = None
    role: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    status: str | None = None
    detail: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0


class AuditActionCount(BaseModel):
    action: str
    count: int


class AuditLogStatsResponse(BaseModel):
    total: int = 0
    success_count: int = 0
    denied_count: int = 0
    failed_count: int = 0
    top_actions: list[AuditActionCount] = Field(default_factory=list)
