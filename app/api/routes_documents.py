from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)

from app.core.deps import get_request_id, require_roles
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentReindexResponse,
    DocumentUploadResponse,
)
from app.services.audit_service import AuditService
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
)


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
document_service = DocumentService()
audit_service = AuditService()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    doc_type: str | None = Form(default=None),
    version: str = Form(default="v1"),
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    if not file.filename:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_upload",
            resource_type="document",
            status="failed",
            detail="文件名不能为空",
        )
        raise HTTPException(status_code=400, detail="文件名不能为空")

    file_bytes = await file.read()
    if not file_bytes:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_upload",
            resource_type="document",
            resource_id=file.filename,
            status="failed",
            detail="上传文件不能为空",
        )
        raise HTTPException(status_code=400, detail="上传文件不能为空")

    try:
        result = document_service.upload_and_index_document(
            file_bytes=file_bytes,
            original_filename=file.filename,
            doc_type=doc_type,
            version=version,
        )
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_upload",
            resource_type="document",
            resource_id=result.get("doc_id"),
            status="success",
            detail=f"filename={result.get('filename')}",
        )
        return result
    except (ValueError, UnicodeError) as exc:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_upload",
            resource_type="document",
            resource_id=file.filename,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_upload",
            resource_type="document",
            resource_id=file.filename,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"文档入库失败: {exc}",
        ) from exc


@router.get("", response_model=DocumentListResponse)
def list_documents(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: dict = Depends(
        require_roles("admin", "engineer", "viewer")
    ),
):
    try:
        documents = document_service.list_documents(status=status_filter)
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
def get_document(
    doc_id: str,
    current_user: dict = Depends(
        require_roles("admin", "engineer", "viewer")
    ),
):
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
def delete_document(
    doc_id: str,
    request: Request,
    current_user: dict = Depends(require_roles("admin")),
):
    try:
        result = document_service.delete_document(doc_id)
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_delete",
            resource_type="document",
            resource_id=doc_id,
            status="success",
            detail=result.get("message"),
        )
        return result
    except DocumentNotFoundError as exc:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_delete",
            resource_type="document",
            resource_id=doc_id,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_delete",
            resource_type="document",
            resource_id=doc_id,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"删除文档失败: {exc}",
        ) from exc


@router.post(
    "/{doc_id}/reindex",
    response_model=DocumentReindexResponse,
)
def reindex_document(
    doc_id: str,
    request: Request,
    current_user: dict = Depends(require_roles("admin")),
):
    try:
        result = document_service.reindex_document(doc_id)
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_reindex",
            resource_type="document",
            resource_id=doc_id,
            status="success",
            detail=result.get("message"),
        )
        return result
    except DocumentNotFoundError as exc:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_reindex",
            resource_type="document",
            resource_id=doc_id,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_reindex",
            resource_type="document",
            resource_id=doc_id,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        audit_service.log_action(
            request_id=get_request_id(request),
            session_id=None,
            username=current_user["username"],
            role=current_user["role"],
            action="document_reindex",
            resource_type="document",
            resource_id=doc_id,
            status="failed",
            detail=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"重建文档索引失败: {exc}",
        ) from exc
