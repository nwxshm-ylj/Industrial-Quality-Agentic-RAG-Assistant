from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

from app.core.config import settings
from app.db.session import engine


def _load_items(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("RAGAS dataset must be a non-empty JSON list")
    return payload


def validate_dataset(path: Path) -> dict[str, int]:
    items = _load_items(path)
    errors: list[str] = []
    question_ids: set[str] = set()
    expected_doc_ids: set[str] = set()
    expected_chunk_ids: set[str] = set()

    for index, item in enumerate(items, start=1):
        question_id = str(item.get("id") or "").strip()
        if not question_id:
            errors.append(f"item {index}: id is required")
        elif question_id in question_ids:
            errors.append(f"item {index}: duplicate id {question_id}")
        question_ids.add(question_id)

        for field in ("question", "reference_answer"):
            if not str(item.get(field) or "").strip():
                errors.append(f"{question_id or index}: {field} is required")

        doc_ids = {
            str(value).strip()
            for value in item.get("expected_doc_ids", [])
            if str(value).strip()
        }
        chunk_ids = {
            str(value).strip()
            for value in item.get("expected_chunk_ids", [])
            if str(value).strip()
        }
        if not doc_ids:
            errors.append(f"{question_id or index}: expected_doc_ids is required")
        if not chunk_ids:
            errors.append(f"{question_id or index}: expected_chunk_ids is required")
        if not item.get("reference_contexts"):
            errors.append(f"{question_id or index}: reference_contexts is required")
        if item.get("evaluation_type") != "single_turn_grounded":
            errors.append(
                f"{question_id or index}: evaluation_type must be "
                "single_turn_grounded"
            )
        expected_doc_ids.update(doc_ids)
        expected_chunk_ids.update(chunk_ids)

    with engine.connect() as connection:
        if expected_doc_ids:
            indexed_docs = set(
                connection.execute(
                    text(
                        """
                        SELECT doc_id
                        FROM documents
                        WHERE status = 'indexed' AND doc_id IN :doc_ids
                        """
                    ).bindparams(bindparam("doc_ids", expanding=True)),
                    {"doc_ids": sorted(expected_doc_ids)},
                ).scalars()
            )
        else:
            indexed_docs = set()

        if expected_chunk_ids:
            chunk_rows = connection.execute(
                text(
                    """
                    SELECT chunk_id, doc_id
                    FROM document_chunks
                    WHERE chunk_id IN :chunk_ids
                    """
                ).bindparams(bindparam("chunk_ids", expanding=True)),
                {"chunk_ids": sorted(expected_chunk_ids)},
            ).mappings().all()
        else:
            chunk_rows = []

    missing_docs = expected_doc_ids - indexed_docs
    if missing_docs:
        errors.append(
            "documents are missing or not indexed: " + ", ".join(sorted(missing_docs))
        )
    found_chunks = {str(row["chunk_id"]): str(row["doc_id"]) for row in chunk_rows}
    missing_chunks = expected_chunk_ids - set(found_chunks)
    if missing_chunks:
        errors.append("chunks are missing: " + ", ".join(sorted(missing_chunks)))

    for item in items:
        item_docs = set(item.get("expected_doc_ids", []))
        for chunk_id in item.get("expected_chunk_ids", []):
            chunk_doc_id = found_chunks.get(chunk_id)
            if chunk_doc_id is not None and chunk_doc_id not in item_docs:
                errors.append(
                    f"{item['id']}: chunk {chunk_id} belongs to unexpected "
                    f"document {chunk_doc_id}"
                )

    if errors:
        raise RuntimeError("RAGAS dataset validation failed:\n- " + "\n- ".join(errors))

    return {
        "questions": len(items),
        "indexed_documents": len(indexed_docs),
        "validated_chunks": len(found_chunks),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate RAGAS gold references against PostgreSQL"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(settings.ragas_dataset_path),
    )
    args = parser.parse_args()
    summary = validate_dataset(args.dataset)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
