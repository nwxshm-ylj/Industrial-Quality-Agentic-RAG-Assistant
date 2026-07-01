import json
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.db.session import engine
from app.rag.chunk_store import refresh_chunk_store_from_db
from app.services.document_service import DocumentService


def verify_infrastructure(service: DocumentService) -> None:
    try:
        with engine.connect() as conn:
            tables = conn.execute(
                text(
                    "SELECT to_regclass('public.documents'), "
                    "to_regclass('public.document_chunks')"
                )
            ).one()
            if not all(tables):
                raise RuntimeError("文档管理数据表尚未初始化")
    except Exception as exc:
        raise RuntimeError(
            "PostgreSQL 不可用，请先启动数据库并运行 "
            "python -m scripts.init_sql_data"
        ) from exc

    try:
        service.vectorstore.client.get_collections()
    except Exception as exc:
        raise RuntimeError(
            "Qdrant 或嵌入模型不可用，请检查 Qdrant、网络和模型配置"
        ) from exc


def main() -> None:
    service = DocumentService()
    verify_infrastructure(service)

    doc_id: str | None = None
    uploaded_path: Path | None = None
    test_token = uuid4().hex
    test_filename = f"kb_test_{test_token}.txt"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temporary_file = Path(temp_dir) / test_filename
            temporary_file.write_text(
                "工业质量知识库管理测试文档。\n"
                f"唯一测试标识：{test_token}\n"
                "轮毂识别异常应优先检查相机曝光、设备标定和规则版本。",
                encoding="utf-8",
            )

            uploaded = service.upload_and_index_document(
                file_bytes=temporary_file.read_bytes(),
                original_filename=temporary_file.name,
                doc_type="TEST",
                version="test-v1",
            )

        doc_id = uploaded.get("doc_id")
        assert doc_id, "上传结果缺少 doc_id"
        uploaded_path = (
            Path("data/uploads")
            / f"{doc_id}_{uploaded['filename']}"
        )

        document = service.get_document(doc_id)
        assert document is not None, "documents 表未查询到上传文档"
        assert document["status"] == "indexed"
        assert document["chunk_count"] > 0

        with engine.connect() as conn:
            chunk_count = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM document_chunks
                    WHERE doc_id = :doc_id
                """),
                {"doc_id": doc_id},
            ).scalar_one()
        assert chunk_count > 0, "document_chunks 表没有对应 chunks"

        documents = service.list_documents()
        assert any(item["doc_id"] == doc_id for item in documents)

        reindexed = service.reindex_document(doc_id)
        assert reindexed["status"] == "indexed"
        assert reindexed["chunk_count"] > 0

        deleted = service.delete_document(doc_id)
        assert deleted["status"] == "deleted"

        deleted_document = service.get_document(doc_id)
        assert deleted_document is not None
        assert deleted_document["status"] == "deleted"
        assert deleted_document["chunk_count"] == 0

        print(json.dumps(
            {
                "uploaded": uploaded,
                "postgres_chunk_count": chunk_count,
                "reindexed": reindexed,
                "deleted": deleted,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))
        print("Document management 验证通过")

    finally:
        cleanup_records = []
        try:
            with engine.connect() as conn:
                cleanup_records = conn.execute(
                    text(
                        "SELECT doc_id, file_path FROM documents "
                        "WHERE original_filename = :original_filename"
                    ),
                    {"original_filename": test_filename},
                ).mappings().all()
        except Exception:
            cleanup_records = []

        for record in cleanup_records:
            cleanup_doc_id = record["doc_id"]
            try:
                service.vectorstore.delete_by_doc_id(cleanup_doc_id)
            except Exception:
                pass

            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "DELETE FROM document_chunks "
                            "WHERE doc_id = :doc_id"
                        ),
                        {"doc_id": cleanup_doc_id},
                    )
                    conn.execute(
                        text("DELETE FROM documents WHERE doc_id = :doc_id"),
                        {"doc_id": cleanup_doc_id},
                    )
            except Exception:
                pass

            record_path = Path(record["file_path"]) if record["file_path"] else None
            if record_path and record_path.exists():
                record_path.unlink()

        if uploaded_path and uploaded_path.exists():
            uploaded_path.unlink()

        try:
            refresh_chunk_store_from_db()
        except Exception:
            pass


if __name__ == "__main__":
    main()
