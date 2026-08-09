from __future__ import annotations

from pathlib import Path

from app.rag.parsing.contracts import ParsedDocument
from app.rag.parsing.exceptions import DocumentParsingError, EmptyDocumentError
from app.rag.structured_parser import (
    parse_docx_document,
    parse_pdf_document,
    parse_pptx_document,
    parse_text_document,
)


class NativeStructuredParser:
    """Adapter for the existing lightweight structured parser implementation."""

    name = "structured-v1"
    version = "structured-v1"
    supported_extensions = frozenset({".md", ".txt", ".pdf", ".docx", ".pptx"})

    def parse(self, path: Path) -> ParsedDocument:
        try:
            if path.suffix.lower() in {".md", ".txt"}:
                raw_document = parse_text_document(path)
            elif path.suffix.lower() == ".pdf":
                raw_document = parse_pdf_document(path)
            elif path.suffix.lower() == ".docx":
                raw_document = parse_docx_document(path)
            else:
                raw_document = parse_pptx_document(path)
        except DocumentParsingError:
            raise
        except ValueError as exc:
            if "文档内容为空" in str(exc):
                raise EmptyDocumentError(str(exc)) from exc
            raise DocumentParsingError(str(exc)) from exc
        except Exception as exc:
            raise DocumentParsingError(f"文档解析失败: {path.name}: {exc}") from exc

        raw_document["parser"] = self.name
        raw_document["parser_name"] = self.name
        raw_document["parser_version"] = self.version
        document = ParsedDocument.from_mapping(raw_document)
        if not document.content or not document.elements:
            raise EmptyDocumentError(f"文档内容为空: {path.name}")
        return document
