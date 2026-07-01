from uuid import uuid4

from fastapi import FastAPI, Request

from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_documents import router as documents_router


app = FastAPI(
    title="Industrial Quality Agentic RAG Assistant",
    description="工业质量知识库与设备异常诊断 RAG 系统",
    version="0.1.0"
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)