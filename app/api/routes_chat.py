import asyncio
import json
from contextvars import Context
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.deps import get_request_id, require_roles
from app.rag.chain import IndustrialRAGChain
from app.rag.graph_chain import IndustrialGraphRAGChain
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.audit_service import AuditService
from app.streaming.events import stream_event_sink


router = APIRouter(prefix="/api/v1", tags=["chat"])
audit_service = AuditService()
_background_stream_tasks: set[asyncio.Task] = set()


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
            retrieval_filters=(
                request.retrieval_filters.model_dump(exclude_none=True)
                if request.retrieval_filters
                else None
            ),
            multimodal_query=(
                request.multimodal_query.model_dump(exclude_none=True)
                if request.multimodal_query
                else None
            ),
            retrieval_mode=request.retrieval_mode,
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
            detail=(
                f"intent={result.get('intent')}; "
                f"retrieval_mode={request.retrieval_mode}"
            ),
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


@router.post("/graph-chat/stream")
async def graph_chat_stream(
    request: ChatRequest,
    http_request: Request,
    current_user: dict = Depends(
        require_roles("admin", "engineer", "viewer")
    ),
):
    request_id = get_request_id(http_request) or str(uuid4())
    session_id = request.session_id or "default"
    username = current_user["username"]
    role = current_user["role"]

    async def event_stream():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()
        completed = object()
        sequence = 0
        accepting_events = True

        def push(event: dict[str, Any]) -> None:
            nonlocal sequence
            if not accepting_events:
                return
            sequence += 1
            payload = {
                **event,
                "sequence": sequence,
                "request_id": request_id,
                "session_id": session_id,
            }
            try:
                loop.call_soon_threadsafe(queue.put_nowait, payload)
            except RuntimeError:
                return

        def run_graph() -> dict:
            graph_chain = IndustrialGraphRAGChain()
            with stream_event_sink(push):
                return graph_chain.invoke(
                    question=request.question,
                    top_k=request.top_k,
                    session_id=session_id,
                    request_id=request_id,
                    user={"username": username, "role": role},
                    retrieval_filters=(
                        request.retrieval_filters.model_dump(exclude_none=True)
                        if request.retrieval_filters
                        else None
                    ),
                    multimodal_query=(
                        request.multimodal_query.model_dump(exclude_none=True)
                        if request.multimodal_query
                        else None
                    ),
                    retrieval_mode=request.retrieval_mode,
                )

        async def execute_graph() -> None:
            try:
                # Run with an isolated context so the graph owns and persists
                # usage telemetry after the HTTP streaming response has started.
                result = await asyncio.to_thread(Context().run, run_graph)
                audit_service.log_action(
                    request_id=request_id,
                    session_id=session_id,
                    username=username,
                    role=role,
                    action="graph_chat",
                    resource_type="conversation",
                    resource_id=session_id,
                    status="success",
                    detail=(
                        f"intent={result.get('intent')}; streaming=true; "
                        f"retrieval_mode={request.retrieval_mode}"
                    ),
                )
                await queue.put(
                    {
                        "event": "result",
                        "sequence": sequence + 1,
                        "request_id": request_id,
                        "session_id": session_id,
                        "response": result,
                    }
                )
                await queue.put(
                    {
                        "event": "done",
                        "sequence": sequence + 2,
                        "request_id": request_id,
                        "session_id": session_id,
                    }
                )
            except PermissionError as exc:
                audit_service.log_action(
                    request_id=request_id,
                    session_id=session_id,
                    username=username,
                    role=role,
                    action="graph_chat",
                    resource_type="conversation",
                    resource_id=session_id,
                    status="denied",
                    detail=str(exc),
                )
                await queue.put(
                    {
                        "event": "error",
                        "sequence": sequence + 1,
                        "request_id": request_id,
                        "session_id": session_id,
                        "status_code": 403,
                        "error_code": "PERMISSION_DENIED",
                        "message": str(exc),
                        "retryable": False,
                    }
                )
            except Exception as exc:
                audit_service.log_action(
                    request_id=request_id,
                    session_id=session_id,
                    username=username,
                    role=role,
                    action="graph_chat",
                    resource_type="conversation",
                    resource_id=session_id,
                    status="failed",
                    detail=str(exc),
                )
                await queue.put(
                    {
                        "event": "error",
                        "sequence": sequence + 1,
                        "request_id": request_id,
                        "session_id": session_id,
                        "status_code": 500,
                        "error_code": type(exc).__name__,
                        "message": (
                            "流式回答生成失败，请使用 request_id 查询服务日志"
                        ),
                        "retryable": True,
                    }
                )
            finally:
                await queue.put(completed)

        worker = asyncio.create_task(execute_graph())
        _background_stream_tasks.add(worker)
        worker.add_done_callback(_background_stream_tasks.discard)

        yield format_sse_event(
            "accepted",
            {
                "sequence": 0,
                "request_id": request_id,
                "session_id": session_id,
                "status": "accepted",
            },
        )

        try:
            while True:
                event = await queue.get()
                if event is completed:
                    break
                event_payload = dict(event)
                event_name = str(event_payload.pop("event"))
                yield format_sse_event(event_name, event_payload)
        finally:
            accepting_events = False

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"
