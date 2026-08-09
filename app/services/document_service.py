import hashlib
import logging
import re
import shutil
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import text

from app.core.config import settings
from app.core.metrics import record_document_operation
from app.core.logger import logger
from app.db.session import engine
from app.multimodal.document_parser import (
    MULTIMODAL_DOCUMENT_EXTENSIONS,
    parse_multimodal_document,
)
from app.multimodal.factory import get_multimodal_embedding_provider
from app.multimodal.ocr import DocumentOcrProvider, get_document_ocr_provider
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.loader import SUPPORTED_DOCUMENT_EXTENSIONS, load_single_document
from app.rag.chunking.layout_chunker import scope_chunk_id
from app.rag.parsing.merge import merge_structured_and_multimodal
from app.rag.search_backends.base import (
    KeywordSearchBackend,
    VectorSearchBackend,
)
from app.rag.search_backends.opensearch_backend import OpenSearchKeywordBackend
from app.rag.search_backends.multimodal_qdrant_backend import (
    MultimodalQdrantSearchBackend,
)
from app.rag.search_backends.qdrant_backend import QdrantVectorSearchBackend
from app.rag.splitter import infer_doc_type, split_docs


DOCUMENT_STATUSES = {"uploaded", "indexed", "deleted", "failed"}
PUBLIC_DOCUMENT_FIELDS = (
    "doc_id",
    "filename",
    "original_filename",
    "doc_type",
    "file_ext",
    "version",
    "status",
    "chunk_count",
    "failed_stage",
    "error_message",
    "created_at",
    "updated_at",
)


class DocumentNotFoundError(LookupError):
    pass


class DocumentService:
    def __init__(
        self,
        uploads_dir: str | Path = "data/uploads",
        vectorstore: VectorSearchBackend | None = None,
        vector_backend: VectorSearchBackend | None = None,
        keyword_backend: KeywordSearchBackend | None = None,
        multimodal_backend: MultimodalQdrantSearchBackend | None = None,
        ocr_provider: DocumentOcrProvider | None = None,
    ):
        self.uploads_dir = Path(uploads_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._vector_backend = vector_backend or vectorstore
        self._keyword_backend = keyword_backend
        self._multimodal_backend = multimodal_backend
        self._ocr_provider = ocr_provider
        self.assets_dir = self.uploads_dir / "assets"

    @property
    def vector_backend(self) -> VectorSearchBackend:
        if self._vector_backend is None:
            provider = get_embedding_provider()
            self._vector_backend = QdrantVectorSearchBackend(
                provider,
                collection_name=settings.qdrant_collection,
                collection_alias=settings.qdrant_collection_alias,
            )
        return self._vector_backend

    @property
    def keyword_backend(self) -> KeywordSearchBackend:
        if self._keyword_backend is None:
            self._keyword_backend = OpenSearchKeywordBackend(
                index_name=(
                    f"{settings.opensearch_index_prefix}_keyword_"
                    f"{settings.keyword_index_version}"
                )
            )
        return self._keyword_backend

    @property
    def vectorstore(self) -> VectorSearchBackend:
        """Backward-compatible alias used by existing integration scripts."""

        return self.vector_backend

    @property
    def multimodal_backend(self) -> MultimodalQdrantSearchBackend:
        if self._multimodal_backend is None:
            self._multimodal_backend = MultimodalQdrantSearchBackend(
                get_multimodal_embedding_provider(),
                collection_name=settings.qdrant_multimodal_collection,
                collection_alias=settings.qdrant_multimodal_collection_alias,
            )
        return self._multimodal_backend

    @property
    def ocr_provider(self) -> DocumentOcrProvider | None:
        if self._ocr_provider is None:
            self._ocr_provider = get_document_ocr_provider()
        return self._ocr_provider

    def upload_and_index_document(
        self,
        file_bytes: bytes,
        original_filename: str,
        doc_type: str | None = None,
        version: str = "v1",
    ) -> dict:
        started_at = perf_counter()
        doc_id = uuid4().hex
        filename = original_filename or "unknown"
        effective_doc_type = doc_type
        normalized_version = version or "v1"
        record_created = False
        operation_id = uuid4().hex
        failed_stage = "upload_start"

        self._log_event(
            "upload_start",
            started_at,
            doc_id=doc_id,
            filename=filename,
            doc_type=effective_doc_type,
            version=normalized_version,
            status="uploaded",
        )

        try:
            if not file_bytes:
                raise ValueError("上传文件不能为空")

            safe_filename, file_ext = self._sanitize_filename(original_filename)
            normalized_version = self._normalize_version(version)
            effective_doc_type = self._normalize_doc_type(
                doc_type or infer_doc_type(safe_filename)
            )
            content_hash = hashlib.sha256(file_bytes).hexdigest()

            duplicate = self._find_duplicate(content_hash)
            if duplicate is not None:
                self._log_event(
                    "document_indexed",
                    started_at,
                    doc_id=duplicate["doc_id"],
                    filename=duplicate["filename"],
                    doc_type=duplicate["doc_type"],
                    version=duplicate["version"],
                    status=duplicate["status"],
                    chunk_count=duplicate["chunk_count"],
                )
                return self._public_document(duplicate)

            stored_filename = f"{doc_id}_{safe_filename}"
            file_path = self.uploads_dir / stored_filename
            self._insert_document(
                doc_id=doc_id,
                filename=safe_filename,
                original_filename=original_filename,
                doc_type=effective_doc_type,
                file_ext=file_ext,
                file_path=str(file_path),
                version=normalized_version,
                content_hash=content_hash,
            )
            record_created = True

            failed_stage = "file_save"
            file_path.write_bytes(file_bytes)
            self._log_event(
                "file_saved",
                started_at,
                doc_id=doc_id,
                filename=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="uploaded",
            )

            failed_stage = "parse"
            parsed_document, assets = self._parse_document_for_indexing(
                file_path=file_path,
                doc_id=doc_id,
                source=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
            )
            self._log_event(
                "document_parsed",
                started_at,
                doc_id=doc_id,
                filename=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="uploaded",
                parser_name=parsed_document.get("parser_name"),
                parser_version=parsed_document.get("parser_version"),
                multimodal_asset_count=len(assets),
                ocr_element_count=parsed_document.get("metadata", {}).get(
                    "ocr_element_count", 0
                ),
            )

            failed_stage = "chunk"
            chunks = self._create_document_chunks(
                parsed_document=parsed_document,
                doc_id=doc_id,
                source=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
            )
            self._log_event(
                "chunks_created",
                started_at,
                doc_id=doc_id,
                filename=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="uploaded",
                chunk_count=len(chunks),
            )

            failed_stage = "postgres"
            self._replace_chunks_in_postgres(doc_id, chunks)
            if assets:
                self._replace_assets_in_postgres(doc_id, assets)
            self._log_event(
                "postgres_written",
                started_at,
                doc_id=doc_id,
                filename=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="uploaded",
                chunk_count=len(chunks),
            )

            failed_stage = "qdrant"
            self.vector_backend.upsert_document_chunks(
                doc_id,
                chunks,
                index_status="staging",
                index_operation_id=operation_id,
            )
            self._log_event(
                "qdrant_written",
                started_at,
                doc_id=doc_id,
                filename=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="uploaded",
                chunk_count=len(chunks),
            )

            failed_stage = "opensearch"
            self.keyword_backend.upsert_document_chunks(
                doc_id,
                chunks,
                index_status="staging",
                index_operation_id=operation_id,
            )
            self._log_event(
                "opensearch_written",
                started_at,
                doc_id=doc_id,
                filename=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="uploaded",
                chunk_count=len(chunks),
            )

            if assets:
                failed_stage = "multimodal_qdrant"
                self.multimodal_backend.upsert_document_assets(
                    doc_id,
                    assets,
                    index_status="staging",
                    index_operation_id=operation_id,
                )
                self._log_event(
                    "multimodal_qdrant_written",
                    started_at,
                    doc_id=doc_id,
                    filename=safe_filename,
                    doc_type=effective_doc_type,
                    version=normalized_version,
                    status="uploaded",
                    chunk_count=len(assets),
                )

            failed_stage = "index_promotion"
            self.vector_backend.set_document_index_status(
                doc_id,
                "indexed",
                index_operation_id=operation_id,
            )
            self.keyword_backend.set_document_index_status(
                doc_id,
                "indexed",
                index_operation_id=operation_id,
            )
            if assets:
                self.multimodal_backend.set_document_index_status(
                    doc_id,
                    "indexed",
                    index_operation_id=operation_id,
                )

            failed_stage = "document_status"
            self._set_document_status(
                doc_id=doc_id,
                status="indexed",
                chunk_count=len(chunks),
            )
            document = self._get_document_record(doc_id)
            if document is None:
                raise RuntimeError(f"文档入库后无法读取元数据: {doc_id}")

            self._log_event(
                "document_indexed",
                started_at,
                doc_id=doc_id,
                filename=safe_filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="indexed",
                chunk_count=len(chunks),
            )
            return self._public_document(document)

        except Exception as exc:
            if record_created:
                self._cleanup_operation_indexes(doc_id, operation_id)
                if failed_stage in {
                    "postgres",
                    "qdrant",
                    "opensearch",
                    "index_promotion",
                    "multimodal_qdrant",
                    "document_status",
                }:
                    self._delete_postgres_chunks(doc_id)
                self._mark_document_failed(
                    doc_id,
                    failed_stage=failed_stage,
                    error_message=str(exc),
                )
            self._log_event(
                "error",
                started_at,
                doc_id=doc_id,
                filename=filename,
                doc_type=effective_doc_type,
                version=normalized_version,
                status="failed",
                error_message=str(exc),
                level=logging.ERROR,
                exc_info=True,
            )
            raise

    def list_documents(self, status: str | None = None) -> list[dict]:
        if status is not None and status not in DOCUMENT_STATUSES:
            raise ValueError(
                f"无效文档状态: {status}。可选值: {sorted(DOCUMENT_STATUSES)}"
            )

        where_clause = "WHERE status = :status" if status else "WHERE status <> 'deleted'"
        query = text(f"""
            SELECT
                doc_id, filename, original_filename, doc_type, file_ext,
                file_path, version, status, chunk_count, content_hash,
                failed_stage, error_message, created_at, updated_at
            FROM documents
            {where_clause}
            ORDER BY updated_at DESC, id DESC
        """)
        parameters = {"status": status} if status else {}

        with engine.connect() as conn:
            rows = conn.execute(query, parameters).mappings().all()

        return [self._public_document(dict(row)) for row in rows]

    def get_document(self, doc_id: str) -> dict | None:
        document = self._get_document_record(doc_id)
        return self._public_document(document) if document else None

    def delete_document(self, doc_id: str) -> dict:
        started_at = perf_counter()
        failed_stage = "qdrant_delete"
        document = self._get_document_record(doc_id)
        if document is None:
            raise DocumentNotFoundError(f"文档不存在: {doc_id}")

        if document["status"] == "deleted":
            return {
                "doc_id": doc_id,
                "status": "deleted",
                "message": "文档已删除",
            }

        try:
            self.vector_backend.delete_by_doc_id(doc_id)
            failed_stage = "opensearch_delete"
            self.keyword_backend.delete_by_doc_id(doc_id)
            if self._document_has_assets(doc_id):
                failed_stage = "multimodal_qdrant_delete"
                self.multimodal_backend.delete_by_doc_id(doc_id)

            failed_stage = "postgres_delete"
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM document_chunks WHERE doc_id = :doc_id"),
                    {"doc_id": doc_id},
                )
                conn.execute(
                    text("DELETE FROM document_assets WHERE doc_id = :doc_id"),
                    {"doc_id": doc_id},
                )
                conn.execute(
                    text("""
                        UPDATE documents
                        SET status = 'deleted', chunk_count = 0,
                            failed_stage = NULL, error_message = NULL,
                            updated_at = NOW()
                        WHERE doc_id = :doc_id
                    """),
                    {"doc_id": doc_id},
                )

            file_path = Path(document["file_path"]) if document.get("file_path") else None
            if file_path and file_path.exists():
                file_path.unlink()
            self._remove_document_asset_files(doc_id)

            self._log_event(
                "document_deleted",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status="deleted",
            )
            return {
                "doc_id": doc_id,
                "status": "deleted",
                "message": "文档及索引已删除",
            }

        except Exception as exc:
            self._mark_document_failed(
                doc_id,
                failed_stage=failed_stage,
                error_message=str(exc),
            )
            self._log_event(
                "error",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status=document["status"],
                chunk_count=document["chunk_count"],
                error_message=str(exc),
                level=logging.ERROR,
                exc_info=True,
            )
            raise

    def reindex_document(self, doc_id: str) -> dict:
        started_at = perf_counter()
        operation_id = uuid4().hex
        failed_stage = "parse"
        promoted = False
        assets: list[dict] = []
        document = self._get_document_record(doc_id)
        if document is None:
            raise DocumentNotFoundError(f"文档不存在: {doc_id}")
        if document["status"] == "deleted":
            raise ValueError(f"已删除文档不能重建索引: {doc_id}")
        if not document.get("file_path"):
            raise ValueError(f"文档缺少文件路径: {doc_id}")

        file_path = Path(document["file_path"])
        if not file_path.exists():
            raise FileNotFoundError(f"原文档不存在，无法重建索引: {file_path}")

        try:
            parsed_document, assets = self._parse_document_for_indexing(
                file_path=file_path,
                doc_id=doc_id,
                source=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                asset_id_namespace=operation_id,
            )
            self._log_event(
                "document_parsed",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status=document["status"],
                parser_name=parsed_document.get("parser_name"),
                parser_version=parsed_document.get("parser_version"),
                multimodal_asset_count=len(assets),
                ocr_element_count=parsed_document.get("metadata", {}).get(
                    "ocr_element_count", 0
                ),
            )

            failed_stage = "chunk"
            chunks = self._create_document_chunks(
                parsed_document=parsed_document,
                doc_id=doc_id,
                source=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                chunk_id_namespace=operation_id,
            )
            self._log_event(
                "chunks_created",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status=document["status"],
                chunk_count=len(chunks),
            )

            failed_stage = "qdrant"
            self.vector_backend.upsert_document_chunks(
                doc_id,
                chunks,
                index_status="staging",
                index_operation_id=operation_id,
            )
            self._log_event(
                "qdrant_written",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status=document["status"],
                chunk_count=len(chunks),
            )

            failed_stage = "opensearch"
            self.keyword_backend.upsert_document_chunks(
                doc_id,
                chunks,
                index_status="staging",
                index_operation_id=operation_id,
            )
            self._log_event(
                "opensearch_written",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status=document["status"],
                chunk_count=len(chunks),
            )

            if assets:
                failed_stage = "multimodal_qdrant"
                self.multimodal_backend.upsert_document_assets(
                    doc_id,
                    assets,
                    index_status="staging",
                    index_operation_id=operation_id,
                )
                self._log_event(
                    "multimodal_qdrant_written",
                    started_at,
                    doc_id=doc_id,
                    filename=document["filename"],
                    doc_type=document["doc_type"],
                    version=document["version"],
                    status=document["status"],
                    chunk_count=len(assets),
                )

            failed_stage = "index_promotion"
            self.vector_backend.set_document_index_status(
                doc_id,
                "indexed",
                index_operation_id=operation_id,
            )
            self.keyword_backend.set_document_index_status(
                doc_id,
                "indexed",
                index_operation_id=operation_id,
            )
            if assets:
                self.multimodal_backend.set_document_index_status(
                    doc_id,
                    "indexed",
                    index_operation_id=operation_id,
                )
            promoted = True

            failed_stage = "old_index_cleanup"
            self.vector_backend.delete_by_doc_id(
                doc_id,
                exclude_operation_id=operation_id,
            )
            self.keyword_backend.delete_by_doc_id(
                doc_id,
                exclude_operation_id=operation_id,
            )
            if assets:
                self.multimodal_backend.delete_by_doc_id(
                    doc_id,
                    exclude_operation_id=operation_id,
                )
            elif self._document_has_assets(doc_id):
                self.multimodal_backend.delete_by_doc_id(doc_id)

            failed_stage = "postgres"
            self._replace_chunks_in_postgres(doc_id, chunks)
            self._replace_assets_in_postgres(doc_id, assets)
            self._log_event(
                "postgres_written",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status=document["status"],
                chunk_count=len(chunks),
            )

            failed_stage = "document_status"
            self._set_document_status(doc_id, "indexed", len(chunks))
            self._log_event(
                "document_reindexed",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status="indexed",
                chunk_count=len(chunks),
            )
            return {
                "doc_id": doc_id,
                "status": "indexed",
                "chunk_count": len(chunks),
                "message": "文档索引重建完成",
            }

        except Exception as exc:
            if not promoted:
                self._cleanup_operation_indexes(doc_id, operation_id)
                for asset in assets:
                    asset_path = asset.get("metadata", {}).get("asset_path")
                    if asset_path and Path(asset_path).exists():
                        Path(asset_path).unlink()
                self._cleanup_empty_asset_dirs(doc_id)
            self._mark_document_failed(
                doc_id,
                failed_stage=failed_stage,
                error_message=str(exc),
            )
            self._log_event(
                "error",
                started_at,
                doc_id=doc_id,
                filename=document["filename"],
                doc_type=document["doc_type"],
                version=document["version"],
                status="failed",
                error_message=str(exc),
                level=logging.ERROR,
                exc_info=True,
            )
            raise

    def _parse_document_for_indexing(
        self,
        *,
        file_path: Path,
        doc_id: str,
        source: str,
        doc_type: str,
        version: str,
        asset_id_namespace: str | None = None,
    ) -> tuple[dict, list[dict]]:
        multimodal_requested = (
            settings.multimodal_enabled or self._multimodal_backend is not None
        )
        structured_document: dict | None = None
        structured_error: Exception | None = None
        try:
            structured_document = load_single_document(
                str(file_path),
                parser_backend=settings.document_parser_backend,
                parser_fallback=settings.document_parser_fallback,
                deepdoc_enabled=settings.deepdoc_enabled,
                deepdoc_runtime_factory=settings.deepdoc_runtime_factory,
                deepdoc_model_dir=settings.deepdoc_model_dir,
                deepdoc_require_model_files=settings.deepdoc_require_model_files,
                deepdoc_zoomin=settings.deepdoc_zoomin,
                deepdoc_max_pages=settings.deepdoc_max_pages,
            )
        except ValueError as exc:
            structured_error = exc

        if (
            multimodal_requested
            and file_path.suffix.lower() in MULTIMODAL_DOCUMENT_EXTENSIONS
        ):
            parsed = parse_multimodal_document(
                file_path,
                doc_id=doc_id,
                source=source,
                doc_type=doc_type,
                version=version,
                assets_root=self.assets_dir,
                ocr_provider=self.ocr_provider,
                asset_id_namespace=asset_id_namespace,
            )
            merged = merge_structured_and_multimodal(structured_document, parsed)
            return merged, parsed["assets"]
        if structured_document is not None:
            return structured_document, []
        if structured_error is not None:
            raise structured_error
        raise ValueError(f"文档解析失败: {source}")

    def _replace_assets_in_postgres(
        self,
        doc_id: str,
        assets: list[dict],
    ) -> None:
        previous_paths = self._get_document_asset_paths(doc_id)
        rows = []
        for asset in assets:
            metadata = asset["metadata"]
            rows.append(
                {
                    "doc_id": doc_id,
                    "asset_id": metadata["asset_id"],
                    "page_number": metadata.get("page_number"),
                    "modality": metadata.get("modality", "unknown"),
                    "text": asset.get("text", ""),
                    "asset_path": metadata.get("asset_path"),
                    "mime_type": metadata.get("mime_type"),
                    "source": metadata.get("source"),
                    "version": metadata.get("version"),
                }
            )
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM document_assets WHERE doc_id = :doc_id"),
                {"doc_id": doc_id},
            )
            if rows:
                conn.execute(
                    text("""
                        INSERT INTO document_assets (
                            doc_id, asset_id, page_number, modality, text,
                            asset_path, mime_type, source, version
                        ) VALUES (
                            :doc_id, :asset_id, :page_number, :modality, :text,
                            :asset_path, :mime_type, :source, :version
                        )
                    """),
                    rows,
                )
        retained_paths = {
            Path(row["asset_path"]).resolve()
            for row in rows
            if row.get("asset_path")
        }
        for previous_path in previous_paths:
            path = Path(previous_path)
            if path.resolve() not in retained_paths and path.exists():
                path.unlink()
        self._cleanup_empty_asset_dirs(doc_id)

    def _document_has_assets(self, doc_id: str) -> bool:
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM document_assets WHERE doc_id = :doc_id"
                ),
                {"doc_id": doc_id},
            ).scalar_one()
        return int(count) > 0

    def _get_document_asset_paths(self, doc_id: str) -> list[str]:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT asset_path FROM document_assets "
                    "WHERE doc_id = :doc_id AND asset_path IS NOT NULL"
                ),
                {"doc_id": doc_id},
            ).all()
        return [str(row[0]) for row in rows]

    def _remove_document_asset_files(self, doc_id: str) -> None:
        asset_dir = self.assets_dir / doc_id
        if asset_dir.exists():
            shutil.rmtree(asset_dir)

    def _cleanup_empty_asset_dirs(self, doc_id: str) -> None:
        asset_dir = self.assets_dir / doc_id
        if not asset_dir.exists():
            return
        for child in asset_dir.iterdir():
            if child.is_dir():
                try:
                    child.rmdir()
                except OSError:
                    pass
        try:
            asset_dir.rmdir()
        except OSError:
            pass

    def _sanitize_filename(self, original_filename: str) -> tuple[str, str]:
        if not original_filename or not original_filename.strip():
            raise ValueError("文件名不能为空")

        base_name = Path(
            original_filename.replace("\\", "/")
        ).name
        safe_name = re.sub(r"[^\w.-]", "_", base_name, flags=re.UNICODE)
        safe_name = safe_name.lstrip(".")
        if not safe_name:
            raise ValueError("文件名无效")

        file_ext = Path(safe_name).suffix.lower()
        if file_ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))
            raise ValueError(
                f"不支持的文档格式: {file_ext or '无扩展名'}。支持格式: {supported}"
            )

        max_stem_length = 220 - len(file_ext)
        stem = Path(safe_name).stem[:max_stem_length]
        return f"{stem}{file_ext}", file_ext

    def _normalize_doc_type(self, doc_type: str) -> str:
        normalized = doc_type.strip() or "GENERAL"
        if len(normalized) > 50:
            raise ValueError("doc_type 长度不能超过 50")
        return normalized

    def _normalize_version(self, version: str) -> str:
        normalized = (version or "v1").strip() or "v1"
        if len(normalized) > 50:
            raise ValueError("version 长度不能超过 50")
        return normalized

    def _find_duplicate(self, content_hash: str) -> dict | None:
        query = text("""
            SELECT
                doc_id, filename, original_filename, doc_type, file_ext,
                file_path, version, status, chunk_count, content_hash,
                failed_stage, error_message, created_at, updated_at
            FROM documents
            WHERE content_hash = :content_hash
              AND status IN ('uploaded', 'indexed')
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        with engine.connect() as conn:
            row = conn.execute(
                query,
                {"content_hash": content_hash},
            ).mappings().first()
        return dict(row) if row else None

    def _insert_document(
        self,
        doc_id: str,
        filename: str,
        original_filename: str,
        doc_type: str,
        file_ext: str,
        file_path: str,
        version: str,
        content_hash: str,
    ) -> None:
        query = text("""
            INSERT INTO documents (
                doc_id, filename, original_filename, doc_type, file_ext,
                file_path, version, status, chunk_count, content_hash
            )
            VALUES (
                :doc_id, :filename, :original_filename, :doc_type, :file_ext,
                :file_path, :version, 'uploaded', 0, :content_hash
            )
        """)
        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "doc_id": doc_id,
                    "filename": filename,
                    "original_filename": original_filename[:255],
                    "doc_type": doc_type,
                    "file_ext": file_ext,
                    "file_path": file_path,
                    "version": version,
                    "content_hash": content_hash,
                },
            )

    def _create_document_chunks(
        self,
        parsed_document: dict,
        doc_id: str,
        source: str,
        doc_type: str,
        version: str,
        chunk_id_namespace: str | None = None,
    ) -> list[dict]:
        chunks = split_docs(
            [
                {
                    "source": source,
                    "content": parsed_document["content"],
                    "file_ext": parsed_document.get("file_ext"),
                    "sections": parsed_document.get("sections"),
                    "elements": parsed_document.get("elements"),
                    "parser": parsed_document.get("parser"),
                    "parser_name": parsed_document.get("parser_name"),
                    "parser_version": parsed_document.get("parser_version"),
                    "metadata": parsed_document.get("metadata", {}),
                }
            ],
            chunk_strategy=settings.document_chunk_strategy,
            target_tokens=settings.document_chunk_target_tokens,
            max_tokens=settings.document_chunk_max_tokens,
            overlap_tokens=settings.document_chunk_overlap_tokens,
        )
        if not chunks:
            raise ValueError(f"文档切分后没有有效内容: {source}")

        for index, chunk in enumerate(chunks):
            base_chunk_id = chunk["metadata"].get("chunk_id") or f"chunk_{index}"
            chunk_id = scope_chunk_id(
                doc_id,
                base_chunk_id,
                operation_id=chunk_id_namespace,
            )
            chunk["metadata"].update({
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "chunk_index": index,
                "source": source,
                "doc_type": doc_type,
                "version": version,
            })
        return chunks

    def _replace_chunks_in_postgres(
        self,
        doc_id: str,
        chunks: list[dict],
    ) -> None:
        insert_query = text("""
            INSERT INTO document_chunks (
                doc_id, chunk_id, chunk_index, text, doc_type, source, version
            )
            VALUES (
                :doc_id, :chunk_id, :chunk_index, :text,
                :doc_type, :source, :version
            )
        """)
        rows = [
            {
                "doc_id": doc_id,
                "chunk_id": chunk["metadata"]["chunk_id"],
                "chunk_index": chunk["metadata"]["chunk_index"],
                "text": chunk["text"],
                "doc_type": chunk["metadata"]["doc_type"],
                "source": chunk["metadata"]["source"],
                "version": chunk["metadata"]["version"],
            }
            for chunk in chunks
        ]

        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM document_chunks WHERE doc_id = :doc_id"),
                {"doc_id": doc_id},
            )
            conn.execute(insert_query, rows)
            conn.execute(
                text("""
                    UPDATE documents
                    SET chunk_count = :chunk_count, updated_at = NOW()
                    WHERE doc_id = :doc_id
                """),
                {"doc_id": doc_id, "chunk_count": len(chunks)},
            )

    def _get_document_record(self, doc_id: str) -> dict | None:
        query = text("""
            SELECT
                doc_id, filename, original_filename, doc_type, file_ext,
                file_path, version, status, chunk_count, content_hash,
                failed_stage, error_message, created_at, updated_at
            FROM documents
            WHERE doc_id = :doc_id
            LIMIT 1
        """)
        with engine.connect() as conn:
            row = conn.execute(query, {"doc_id": doc_id}).mappings().first()
        return dict(row) if row else None

    def _set_document_status(
        self,
        doc_id: str,
        status: str,
        chunk_count: int | None = None,
    ) -> None:
        if status not in DOCUMENT_STATUSES:
            raise ValueError(f"无效文档状态: {status}")

        if chunk_count is None:
            query = text("""
                UPDATE documents
                SET status = :status,
                    failed_stage = NULL,
                    error_message = NULL,
                    updated_at = NOW()
                WHERE doc_id = :doc_id
            """)
            parameters = {"doc_id": doc_id, "status": status}
        else:
            query = text("""
                UPDATE documents
                SET status = :status,
                    chunk_count = :chunk_count,
                    failed_stage = NULL,
                    error_message = NULL,
                    updated_at = NOW()
                WHERE doc_id = :doc_id
            """)
            parameters = {
                "doc_id": doc_id,
                "status": status,
                "chunk_count": chunk_count,
            }

        with engine.begin() as conn:
            conn.execute(query, parameters)

    def _mark_document_failed(
        self,
        doc_id: str,
        *,
        failed_stage: str,
        error_message: str,
    ) -> None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE documents
                        SET status = 'failed',
                            failed_stage = :failed_stage,
                            error_message = :error_message,
                            updated_at = NOW()
                        WHERE doc_id = :doc_id
                    """),
                    {
                        "doc_id": doc_id,
                        "failed_stage": failed_stage[:100],
                        "error_message": error_message,
                    },
                )
        except Exception as exc:
            logger.error(
                "document_status_update_failed",
                extra={
                    "event_data": {
                        "event": "error",
                        "doc_id": doc_id,
                        "filename": None,
                        "doc_type": None,
                        "version": None,
                        "status": "failed",
                        "chunk_count": 0,
                        "latency_ms": 0.0,
                        "error_message": str(exc),
                    }
                },
                exc_info=True,
            )

    def _cleanup_operation_indexes(
        self,
        doc_id: str,
        operation_id: str,
    ) -> None:
        for backend_name, backend_getter in (
            ("qdrant", lambda: self.vector_backend),
            ("opensearch", lambda: self.keyword_backend),
            *(
                (("multimodal_qdrant", lambda: self.multimodal_backend),)
                if settings.multimodal_enabled
                or self._multimodal_backend is not None
                else ()
            ),
        ):
            try:
                backend = backend_getter()
                backend.delete_by_doc_id(
                    doc_id,
                    index_operation_id=operation_id,
                )
            except Exception as cleanup_error:
                logger.error(
                    "document_index_compensation_failed",
                    extra={
                        "event_data": {
                            "event": "error",
                            "doc_id": doc_id,
                            "backend": backend_name,
                            "operation_id": operation_id,
                            "status": "failed",
                            "error_message": str(cleanup_error),
                        }
                    },
                    exc_info=True,
                )

    def _delete_postgres_chunks(self, doc_id: str) -> None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM document_chunks WHERE doc_id = :doc_id"),
                    {"doc_id": doc_id},
                )
                conn.execute(
                    text("DELETE FROM document_assets WHERE doc_id = :doc_id"),
                    {"doc_id": doc_id},
                )
                conn.execute(
                    text("""
                        UPDATE documents
                        SET chunk_count = 0, updated_at = NOW()
                        WHERE doc_id = :doc_id
                    """),
                    {"doc_id": doc_id},
                )
            self._remove_document_asset_files(doc_id)
        except Exception as cleanup_error:
            logger.error(
                "document_postgres_compensation_failed",
                extra={
                    "event_data": {
                        "event": "error",
                        "doc_id": doc_id,
                        "backend": "postgres",
                        "status": "failed",
                        "error_message": str(cleanup_error),
                    }
                },
                exc_info=True,
            )

    def _public_document(self, document: dict) -> dict:
        return {
            field: document.get(field)
            for field in PUBLIC_DOCUMENT_FIELDS
        }

    def _log_event(
        self,
        event: str,
        started_at: float,
        *,
        doc_id: str,
        filename: str,
        doc_type: str | None,
        version: str,
        status: str,
        chunk_count: int = 0,
        error_message: str | None = None,
        level: int = logging.INFO,
        exc_info: bool = False,
    ) -> None:
        latency_ms = (perf_counter() - started_at) * 1000
        record_document_operation(
            operation=event,
            status=status,
            latency_ms=latency_ms,
        )
        logger.log(
            level,
            event,
            extra={
                "event_data": {
                    "event": event,
                    "doc_id": doc_id,
                    "filename": filename,
                    "doc_type": doc_type,
                    "version": version,
                    "status": status,
                    "chunk_count": chunk_count,
                    "latency_ms": round(latency_ms, 2),
                    "error_message": error_message,
                    "embedding_provider": settings.embedding_provider,
                    "embedding_model": settings.qwen_embedding_model,
                    "embedding_dimension": settings.qwen_embedding_dimension,
                    "embedding_index_version": settings.embedding_index_version,
                }
            },
            exc_info=exc_info,
        )
