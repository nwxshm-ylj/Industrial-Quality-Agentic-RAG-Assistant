from __future__ import annotations

from pathlib import Path

from app.rag.parsing.router import get_document_parser_router


SUPPORTED_DOCUMENT_EXTENSIONS = set(
    get_document_parser_router().supported_extensions
)


def load_single_document(
    file_path: str,
    *,
    parser_backend: str | None = None,
    parser_fallback: str = "native",
    deepdoc_enabled: bool = False,
    deepdoc_runtime_factory: str | None = None,
    deepdoc_model_dir: str | None = None,
    deepdoc_require_model_files: bool = True,
    deepdoc_zoomin: int = 3,
    deepdoc_max_pages: int = 2000,
) -> dict:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"文档不存在: {path}")

    backend = (parser_backend or "native").strip().lower()
    fallback = (parser_fallback or "").strip().lower()
    if backend not in {"auto", "native", "deepdoc"}:
        raise ValueError(f"不支持的解析后端: {parser_backend}")
    if fallback not in {"", "native"}:
        raise ValueError(f"不支持的解析回退后端: {parser_fallback}")

    router = get_document_parser_router(
        deepdoc_enabled=deepdoc_enabled,
        deepdoc_runtime_factory=deepdoc_runtime_factory,
        deepdoc_model_dir=deepdoc_model_dir,
        deepdoc_require_model_files=deepdoc_require_model_files,
        deepdoc_zoomin=deepdoc_zoomin,
        deepdoc_max_pages=deepdoc_max_pages,
    )
    preferred_parser = None
    fallback_parser = None
    if backend == "native":
        preferred_parser = "structured-v1"
    elif backend == "deepdoc":
        preferred_parser = "deepdoc"
        fallback_parser = "structured-v1" if fallback == "native" else None
    elif deepdoc_enabled and path.suffix.lower() == ".pdf":
        preferred_parser = "deepdoc"
        fallback_parser = "structured-v1" if fallback == "native" else None

    return router.parse(
        path,
        parser_name=preferred_parser,
        fallback_parser_name=fallback_parser,
    ).to_dict()


def load_markdown_docs(folder: str):
    docs = []

    for path in Path(folder).glob("*.md"):
        text = path.read_text(encoding="utf-8")

        docs.append({
            "source": path.name,
            "content": text
        })

    return docs
