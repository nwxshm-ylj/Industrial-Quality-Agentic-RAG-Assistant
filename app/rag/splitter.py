from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.traceability.taxonomy import infer_document_type

from app.rag.chunking.layout_chunker import LayoutChunker, LayoutChunkerConfig
from app.rag.chunking.token_counter import TokenCounter


LEGACY_CHUNK_SIZE = 500
LEGACY_CHUNK_OVERLAP = 80
STRUCTURED_CHUNK_SIZE = 700
STRUCTURED_CHUNK_OVERLAP = 100
STRUCTURED_SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    "；",
    "！",
    "？",
    ". ",
    " ",
    "",
]


def split_docs(
    raw_docs: list[dict],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    chunk_strategy: str | None = None,
    target_tokens: int = 384,
    max_tokens: int = 512,
    overlap_tokens: int = 48,
    token_counter: TokenCounter | None = None,
) -> list[dict]:
    """Split documents while preserving the legacy raw-doc ingestion contract.

    Documents returned by ``load_single_document`` include structured sections and
    use heading/page/table-aware splitting. ``load_markdown_docs`` keeps its
    existing 500/80 recursive splitting behavior for scripts/ingest_docs.py.
    """

    use_legacy_structured_splitter = (
        chunk_strategy not in {None, "layout_token_v2"}
        or chunk_size is not None
        or chunk_overlap is not None
    )
    if chunk_strategy not in {None, "layout_token_v2", "structured_char_v1"}:
        raise ValueError(f"unsupported chunk strategy: {chunk_strategy}")
    if use_legacy_structured_splitter:
        resolved_chunk_size = chunk_size or STRUCTURED_CHUNK_SIZE
        resolved_chunk_overlap = (
            STRUCTURED_CHUNK_OVERLAP if chunk_overlap is None else chunk_overlap
        )
        _validate_chunk_settings(resolved_chunk_size, resolved_chunk_overlap)
        layout_chunker = None
    else:
        resolved_chunk_size = STRUCTURED_CHUNK_SIZE
        resolved_chunk_overlap = STRUCTURED_CHUNK_OVERLAP
        layout_chunker = LayoutChunker(
            LayoutChunkerConfig(
                target_tokens=target_tokens,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            ),
            token_counter=token_counter,
        )

    chunks: list[dict] = []
    for doc in raw_docs:
        if doc.get("elements") or doc.get("sections"):
            if layout_chunker is not None:
                doc_chunks = layout_chunker.split_document(doc)
            else:
                doc_chunks = _split_structured_document(
                    doc,
                    chunk_size=resolved_chunk_size,
                    chunk_overlap=resolved_chunk_overlap,
                )
        else:
            doc_chunks = _split_legacy_document(doc)

        for index, chunk in enumerate(doc_chunks):
            chunk["metadata"].setdefault(
                "chunk_id",
                f"{doc['source']}_{index}",
            )
        chunks.extend(doc_chunks)
    return chunks


def _split_legacy_document(doc: dict) -> list[dict]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=LEGACY_CHUNK_SIZE,
        chunk_overlap=LEGACY_CHUNK_OVERLAP,
        separators=["\n## ", "\n# ", "\n", "。", ".", " "],
    )
    return [
        {
            "text": text,
            "metadata": {
                "source": doc["source"],
                "doc_type": infer_doc_type(doc["source"]),
                "section_type": "legacy_text",
            },
        }
        for text in splitter.split_text(doc["content"])
        if text.strip()
    ]


def _split_structured_document(
    doc: dict,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    chunks: list[dict] = []
    text_sections: list[dict[str, Any]] = []
    current_key: tuple[Any, ...] | None = None

    def flush_text_sections() -> None:
        nonlocal text_sections
        if not text_sections:
            return
        chunks.extend(
            _split_text_section_group(
                doc,
                text_sections,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
        text_sections = []

    for section in doc["sections"]:
        section_type = section.get("section_type", "paragraph")
        if section_type == "heading":
            flush_text_sections()
            current_key = None
            continue
        if section_type == "table":
            flush_text_sections()
            current_key = None
            chunks.extend(
                _split_table_section(
                    doc,
                    section,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
            )
            continue

        key = (
            tuple(section.get("heading_path") or []),
            section.get("page_number"),
        )
        if current_key is not None and key != current_key:
            flush_text_sections()
        current_key = key
        text_sections.append(section)

    flush_text_sections()
    return chunks


def _split_text_section_group(
    doc: dict,
    sections: list[dict],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    first = sections[0]
    heading_path = _clean_heading_path(first.get("heading_path"))
    page_number = first.get("page_number")
    prefix = _context_prefix(heading_path, page_number)
    content = "\n\n".join(
        section.get("text", "").strip()
        for section in sections
        if section.get("text", "").strip()
    )
    if not content:
        return []

    available_size = max(120, chunk_size - len(prefix))
    content_splitter = RecursiveCharacterTextSplitter(
        chunk_size=available_size,
        chunk_overlap=min(chunk_overlap, max(0, available_size // 3)),
        separators=STRUCTURED_SEPARATORS,
    )
    return [
        {
            "text": f"{prefix}{text}" if prefix else text,
            "metadata": _base_metadata(
                doc,
                section_type="text",
                heading_path=heading_path,
                page_number=page_number,
            ),
        }
        for text in content_splitter.split_text(content)
        if text.strip()
    ]


def _split_table_section(
    doc: dict,
    section: dict,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    heading_path = _clean_heading_path(section.get("heading_path"))
    page_number = section.get("page_number")
    prefix = _context_prefix(heading_path, page_number)
    table_text = section.get("text", "").strip()
    if not table_text:
        return []

    metadata = _base_metadata(
        doc,
        section_type="table",
        heading_path=heading_path,
        page_number=page_number,
        table_index=section.get("table_index"),
    )
    if len(prefix) + len(table_text) <= chunk_size:
        return [{"text": f"{prefix}{table_text}", "metadata": metadata}]

    lines = [line for line in table_text.splitlines() if line.strip()]
    if len(lines) < 3:
        return _split_oversized_table_text(
            prefix,
            table_text,
            metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    header = lines[:2]
    rows = lines[2:]
    chunks: list[dict] = []
    current = list(header)
    for row in rows:
        candidate = "\n".join(current + [row])
        if len(prefix) + len(candidate) > chunk_size and len(current) > 2:
            current_text = "\n".join(current)
            chunks.append(
                {
                    "text": f"{prefix}{current_text}",
                    "metadata": dict(metadata),
                }
            )
            current = list(header)

        single_row_table = "\n".join(header + [row])
        if len(prefix) + len(single_row_table) > chunk_size:
            chunks.extend(
                _split_oversized_table_text(
                    prefix,
                    single_row_table,
                    metadata,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
            )
            continue
        current.append(row)
    if len(current) > 2:
        current_text = "\n".join(current)
        chunks.append({"text": f"{prefix}{current_text}", "metadata": dict(metadata)})

    if not chunks:
        return _split_oversized_table_text(
            prefix,
            table_text,
            metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    return chunks


def _split_oversized_table_text(
    prefix: str,
    table_text: str,
    metadata: dict,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    available_size = max(120, chunk_size - len(prefix))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=available_size,
        chunk_overlap=min(chunk_overlap, available_size // 3),
        separators=["\n", "；", ";", "。", " ", ""],
    )
    return [
        {"text": f"{prefix}{text}", "metadata": dict(metadata)}
        for text in splitter.split_text(table_text)
        if text.strip()
    ]


def _base_metadata(
    doc: dict,
    *,
    section_type: str,
    heading_path: list[str],
    page_number: int | None,
    table_index: int | None = None,
) -> dict:
    return {
        "source": doc["source"],
        "doc_type": infer_doc_type(doc["source"]),
        "file_ext": doc.get("file_ext"),
        "parser": doc.get("parser", "structured-v1"),
        "section_type": section_type,
        "heading_path": " > ".join(heading_path),
        "page_number": page_number,
        "table_index": table_index,
    }


def _context_prefix(heading_path: Iterable[str], page_number: int | None) -> str:
    values = []
    heading = " > ".join(value for value in heading_path if value)
    if heading:
        values.append(f"[章节] {heading}")
    if page_number is not None:
        values.append(f"[页码] {page_number}")
    return "\n".join(values) + ("\n" if values else "")


def _clean_heading_path(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(">") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _validate_chunk_settings(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size < 120:
        raise ValueError("chunk_size must be at least 120 characters")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be non-negative and smaller than chunk_size"
        )


def infer_doc_type(filename: str) -> str:
    return infer_document_type(filename)
