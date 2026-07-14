from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.deps import get_request_id, require_roles
from app.schemas.evaluation import (
    EvalRunListResponse,
    EvalRunResponse,
    RetrievalEvalRunListResponse,
    RetrievalEvalRunRequest,
    RetrievalEvalRunResponse,
)
from app.services.evaluation_service import EvaluationService
from app.services.retrieval_evaluation_service import (
    RetrievalEvaluationService,
)


router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])
evaluation_service = EvaluationService()
retrieval_evaluation_service = RetrievalEvaluationService()


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


@router.post(
    "/retrieval/run",
    response_model=RetrievalEvalRunResponse,
)
def run_retrieval_evaluation(
    payload: RetrievalEvalRunRequest,
    request: Request,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        return retrieval_evaluation_service.run_evaluation(
            username=current_user["username"],
            role=current_user["role"],
            request_id=get_request_id(request),
            top_k=payload.top_k,
            k_values=payload.k_values,
            max_questions=payload.max_questions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/retrieval/runs",
    response_model=RetrievalEvalRunListResponse,
)
def list_retrieval_evaluation_runs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        runs = retrieval_evaluation_service.list_runs(
            limit=limit,
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            request_id=get_request_id(request),
        )
        return {"runs": runs, "total": len(runs)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/retrieval/runs/{run_id}",
    response_model=RetrievalEvalRunResponse,
)
def get_retrieval_evaluation_run(
    run_id: str,
    request: Request,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        result = retrieval_evaluation_service.get_run(
            run_id,
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            request_id=get_request_id(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Retrieval evaluation not found")
    return result
