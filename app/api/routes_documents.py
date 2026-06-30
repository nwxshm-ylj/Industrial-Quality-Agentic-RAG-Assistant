from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentReindexResponse,
    DocumentUploadResponse,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
)


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
document_service = DocumentService()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str | None = Form(default=None),
    version: str = Form(default="v1"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件不能为空")

    try:
        return document_service.upload_and_index_document(
            file_bytes=file_bytes,
            original_filename=file.filename,
            doc_type=doc_type,
            version=version,
        )
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"文档入库失败: {exc}",
        ) from exc


@router.get("", response_model=DocumentListResponse)
def list_documents(
    status: str | None = Query(default=None),
):
    try:
        documents = document_service.list_documents(status=status)
        return {
            "documents": documents,
            "total": len(documents),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"查询文档列表失败: {exc}",
        ) from exc


@router.get("/{doc_id}", response_model=DocumentInfo)
def get_document(doc_id: str):
    try:
        document = document_service.get_document(doc_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"查询文档失败: {exc}",
        ) from exc

    if document is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    return document


@router.delete(
    "/{doc_id}",
    response_model=DocumentDeleteResponse,
)
def delete_document(doc_id: str):
    try:
        return document_service.delete_document(doc_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"删除文档失败: {exc}",
        ) from exc


@router.post(
    "/{doc_id}/reindex",
    response_model=DocumentReindexResponse,
)
def reindex_document(doc_id: str):
    try:
        return document_service.reindex_document(doc_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"重建文档索引失败: {exc}",
        ) from exc
