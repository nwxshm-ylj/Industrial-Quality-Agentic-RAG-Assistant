from fastapi import FastAPI

from app.api.routes_chat import router as chat_router
from app.api.routes_documents import router as documents_router


app = FastAPI(
    title="Industrial Quality Agentic RAG Assistant",
    description="工业质量知识库与设备异常诊断 RAG 系统",
    version="0.1.0"
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(documents_router)