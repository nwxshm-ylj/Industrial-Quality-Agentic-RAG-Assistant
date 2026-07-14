from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import require_roles
from app.schemas.observability import (
    IntentUsageResponse,
    ModelUsageResponse,
    RequestUsageDetailsResponse,
    RetrievalUsageResponse,
    UsageOverviewResponse,
    UsageTimeseriesResponse,
)
from app.services.usage_service import UsageService


router = APIRouter(
    prefix="/api/v1/observability",
    tags=["observability"],
)
usage_service = UsageService()


@router.get(
    "/requests/{request_id}",
    response_model=RequestUsageDetailsResponse,
)
def get_request_usage(
    request_id: str,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    result = usage_service.get_request_details(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Request usage not found")
    return result


@router.get("/analytics/overview", response_model=UsageOverviewResponse)
def get_usage_overview(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    start_at, end_at = _normalize_range(start_at, end_at)
    return usage_service.get_overview(start_at=start_at, end_at=end_at)


@router.get("/analytics/timeseries", response_model=UsageTimeseriesResponse)
def get_usage_timeseries(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    granularity: str = Query(default="day", pattern="^(hour|day)$"),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    start_at, end_at = _normalize_range(start_at, end_at)
    return {
        "items": usage_service.get_timeseries(
            start_at=start_at,
            end_at=end_at,
            granularity=granularity,
        )
    }


@router.get("/analytics/models", response_model=ModelUsageResponse)
def get_model_usage(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    start_at, end_at = _normalize_range(start_at, end_at)
    return {
        "items": usage_service.get_model_usage(
            start_at=start_at,
            end_at=end_at,
        )
    }


@router.get("/analytics/intents", response_model=IntentUsageResponse)
def get_intent_usage(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    start_at, end_at = _normalize_range(start_at, end_at)
    return {
        "items": usage_service.get_intent_usage(
            start_at=start_at,
            end_at=end_at,
        )
    }


@router.get("/analytics/retrieval", response_model=RetrievalUsageResponse)
def get_retrieval_usage(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    start_at, end_at = _normalize_range(start_at, end_at)
    return {
        "items": usage_service.get_retrieval_usage(
            start_at=start_at,
            end_at=end_at,
        )
    }


def _normalize_range(
    start_at: datetime | None,
    end_at: datetime | None,
) -> tuple[datetime, datetime]:
    resolved_end = end_at or datetime.now(timezone.utc)
    resolved_start = start_at or (resolved_end - timedelta(days=7))

    if resolved_start.tzinfo is None:
        resolved_start = resolved_start.replace(tzinfo=timezone.utc)
    if resolved_end.tzinfo is None:
        resolved_end = resolved_end.replace(tzinfo=timezone.utc)
    if resolved_start > resolved_end:
        raise HTTPException(
            status_code=400,
            detail="start_at must not be later than end_at",
        )
    return resolved_start, resolved_end
