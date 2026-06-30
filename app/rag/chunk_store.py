import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text


DEFAULT_CHUNK_PATH = "data/processed/chunks.json"


def save_chunks(chunks: list[dict], path: str = DEFAULT_CHUNK_PATH) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = file_path.with_name(
        f".{file_path.name}.{uuid4().hex}.tmp"
    )

    try:
        with temporary_path.open("w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        temporary_path.replace(file_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_chunks(path: str = DEFAULT_CHUNK_PATH) -> list[dict]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"未找到 chunks 文件: {file_path}. 请先运行 python -m scripts.ingest_docs"
        )

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def refresh_chunk_store_from_db(
    path: str = DEFAULT_CHUNK_PATH,
) -> list[dict]:
    from app.db.session import engine

    file_path = Path(path)
    existing_chunks = load_chunks(path) if file_path.exists() else []
    legacy_chunks = [
        chunk
        for chunk in existing_chunks
        if not chunk.get("metadata", {}).get("doc_id")
    ]

    query = text("""
        SELECT
            dc.doc_id,
            dc.chunk_id,
            dc.chunk_index,
            dc.text,
            dc.doc_type,
            dc.source,
            dc.version
        FROM document_chunks AS dc
        JOIN documents AS d ON d.doc_id = dc.doc_id
        WHERE d.status = 'indexed'
        ORDER BY d.created_at ASC, dc.chunk_index ASC
    """)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    managed_chunks = [
        {
            "text": row["text"],
            "metadata": {
                "doc_id": row["doc_id"],
                "chunk_id": row["chunk_id"],
                "chunk_index": row["chunk_index"],
                "doc_type": row["doc_type"],
                "source": row["source"],
                "version": row["version"],
            },
        }
        for row in rows
    ]

    synchronized_chunks = legacy_chunks + managed_chunks
    save_chunks(synchronized_chunks, path)
    return synchronized_chunks
