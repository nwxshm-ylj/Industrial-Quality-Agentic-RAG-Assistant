from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.deps import get_request_id, require_roles
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackItem,
    FeedbackResponse,
    FeedbackStatsResponse,
)
from app.services.feedback_service import FeedbackService


router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])
feedback_service = FeedbackService()


@router.post("", response_model=FeedbackResponse)
def create_feedback(
    payload: FeedbackCreateRequest,
    request: Request,
    current_user: dict = Depends(
        require_roles("admin", "engineer", "viewer")
    ),
):
    request_id = payload.request_id or get_request_id(request)
    try:
        return feedback_service.create_feedback(
            request_id=request_id,
            session_id=payload.session_id,
            username=current_user["username"],
            role=current_user["role"],
            question=payload.question,
            answer=payload.answer,
            rating=payload.rating,
            comment=payload.comment,
            intent=payload.intent,
            citations=payload.citations,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"记录反馈失败: {exc}",
        ) from exc


@router.get("", response_model=list[FeedbackItem])
def list_feedback(
    request: Request,
    rating: str | None = Query(default=None),
    username_filter: str | None = Query(default=None, alias="username"),
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        return feedback_service.list_feedback(
            rating=rating,
            username=username_filter,
            limit=limit,
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            request_id=get_request_id(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"查询反馈失败: {exc}",
        ) from exc


@router.get("/stats", response_model=FeedbackStatsResponse)
def get_feedback_stats(
    request: Request,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        return feedback_service.get_feedback_stats(
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            request_id=get_request_id(request),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"查询反馈统计失败: {exc}",
        ) from exc
