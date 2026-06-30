from pathlib import Path


SUPPORTED_DOCUMENT_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}


def load_single_document(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"文档不存在: {path}")

    file_ext = path.suffix.lower()
    if file_ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))
        raise ValueError(
            f"不支持的文档格式: {file_ext or '无扩展名'}。支持格式: {supported}"
        )

    if file_ext in {".md", ".txt"}:
        content = path.read_text(encoding="utf-8")
    elif file_ext == ".pdf":
        content = _load_pdf(path)
    else:
        content = _load_docx(path)

    content = content.strip()
    if not content:
        raise ValueError(f"文档内容为空: {path.name}")

    return {
        "source": path.name,
        "content": content,
        "file_ext": file_ext,
    }


def _load_pdf(path: Path) -> str:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf

    with pymupdf.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def _load_docx(path: Path) -> str:
    from docx import Document

    document = Document(path)
    return "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    )


def load_markdown_docs(folder: str):
    docs = []

    for path in Path(folder).glob("*.md"):
        text = path.read_text(encoding="utf-8")

        docs.append({
            "source": path.name,
            "content": text
        })

    return docs
