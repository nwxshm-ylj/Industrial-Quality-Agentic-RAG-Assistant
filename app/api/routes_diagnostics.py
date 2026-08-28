from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import require_roles
from app.schemas.observability import RequestDiagnosticsResponse
from app.services.usage_service import UsageService


router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])
usage_service = UsageService()


@router.get(
    "/requests/{request_id}",
    response_model=RequestDiagnosticsResponse,
)
def get_request_diagnostics(
    request_id: str,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    result = usage_service.get_request_diagnostics(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Request diagnostics not found")
    return result
