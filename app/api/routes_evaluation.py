from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.deps import get_request_id, require_roles
from app.schemas.evaluation import (
    EvalRunListResponse,
    EvalRunResponse,
)
from app.services.evaluation_service import EvaluationService


router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])
evaluation_service = EvaluationService()


@router.post("/run", response_model=EvalRunResponse)
def run_evaluation(
    request: Request,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        return evaluation_service.run_evaluation(
            username=current_user["username"],
            role=current_user["role"],
            request_id=get_request_id(request),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"运行评估失败: {exc}",
        ) from exc


@router.get("/runs", response_model=EvalRunListResponse)
def list_eval_runs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        runs = evaluation_service.list_eval_runs(
            limit=limit,
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            request_id=get_request_id(request),
        )
        return {"runs": runs, "total": len(runs)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"查询评估运行失败: {exc}",
        ) from exc


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_eval_run(
    run_id: str,
    request: Request,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        result = evaluation_service.get_eval_run(
            run_id,
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            request_id=get_request_id(request),
            audit_view=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"查询评估详情失败: {exc}",
        ) from exc

    if result is None:
        raise HTTPException(status_code=404, detail=f"评估运行不存在: {run_id}")
    return result
