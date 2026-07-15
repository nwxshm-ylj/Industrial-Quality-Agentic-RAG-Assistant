from datetime import datetime
from time import perf_counter

from fastapi import APIRouter, Depends, Query, Request

from app.core.deps import get_request_id, require_roles
from app.core.logger import log_business_event
from app.schemas.audit import AuditLogListResponse, AuditLogStatsResponse
from app.services.audit_service import AuditService


router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])
audit_service = AuditService()


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    request: Request,
    username: str | None = Query(default=None, max_length=100),
    action: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=50),
    request_id: str | None = Query(default=None, max_length=100),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_roles("admin")),
):
    started_at = perf_counter()
    result = audit_service.list_logs(
        username=username,
        action=action,
        status=status,
        request_id=request_id,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        offset=offset,
    )
    log_business_event(
        "audit_log_list_queried",
        request_id=get_request_id(request),
        username=current_user["username"],
        role=current_user["role"],
        latency_ms=(perf_counter() - started_at) * 1000,
        result_count=len(result["items"]),
        total=result["total"],
    )
    return result


@router.get("/stats", response_model=AuditLogStatsResponse)
def get_audit_log_stats(
    request: Request,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    current_user: dict = Depends(require_roles("admin")),
):
    started_at = perf_counter()
    result = audit_service.get_stats(start_at=start_at, end_at=end_at)
    log_business_event(
        "audit_log_stats_queried",
        request_id=get_request_id(request),
        username=current_user["username"],
        role=current_user["role"],
        latency_ms=(perf_counter() - started_at) * 1000,
        total=result["total"],
    )
    return result
