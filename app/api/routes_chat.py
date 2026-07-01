from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.deps import get_request_id, require_roles
from app.rag.chain import IndustrialRAGChain
from app.rag.graph_chain import IndustrialGraphRAGChain
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.audit_service import AuditService


router = APIRouter(prefix="/api/v1", tags=["chat"])
audit_service = AuditService()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        rag_chain = IndustrialRAGChain()
        return rag_chain.invoke(
            question=request.question,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/graph-chat", response_model=ChatResponse)
def graph_chat(
    request: ChatRequest,
    http_request: Request,
    current_user: dict = Depends(
        require_roles("admin", "engineer", "viewer")
    ),
):
    request_id = get_request_id(http_request) or str(uuid4())
    graph_chain = IndustrialGraphRAGChain()

    try:
        result = graph_chain.invoke(
            question=request.question,
            top_k=request.top_k,
            session_id=request.session_id,
            request_id=request_id,
            user={
                "username": current_user["username"],
                "role": current_user["role"],
            },
        )
        audit_service.log_action(
            request_id=request_id,
            session_id=request.session_id,
            username=current_user["username"],
            role=current_user["role"],
            action="graph_chat",
            resource_type="conversation",
            resource_id=request.session_id,
            status="success",
            detail=f"intent={result.get('intent')}",
        )
        return result

    except PermissionError as exc:
        audit_service.log_action(
            request_id=request_id,
            session_id=request.session_id,
            username=current_user["username"],
            role=current_user["role"],
            action="graph_chat",
            resource_type="conversation",
            resource_id=request.session_id,
            status="denied",
            detail=str(exc),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    except Exception as exc:
        audit_service.log_action(
            request_id=request_id,
            session_id=request.session_id,
            username=current_user["username"],
            role=current_user["role"],
            action="graph_chat",
            resource_type="conversation",
            resource_id=request.session_id,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
