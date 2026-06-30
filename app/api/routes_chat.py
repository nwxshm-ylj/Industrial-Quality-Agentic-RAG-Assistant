from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.rag.chain import IndustrialRAGChain
from app.rag.graph_chain import IndustrialGraphRAGChain


router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        rag_chain = IndustrialRAGChain()

        result = rag_chain.invoke(
            question=request.question,
            top_k=request.top_k
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/graph-chat", response_model=ChatResponse)
def graph_chat(request: ChatRequest):
    request_id = str(uuid4())

    try:
        graph_chain = IndustrialGraphRAGChain()

        result = graph_chain.invoke(
            question=request.question,
            top_k=request.top_k,
            session_id=request.session_id,
            request_id=request_id,
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
