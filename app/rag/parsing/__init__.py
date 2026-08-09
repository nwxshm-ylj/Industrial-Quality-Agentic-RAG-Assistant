"""Document parsing contracts and parser routing."""

from app.rag.parsing.contracts import DocumentElement, ParsedDocument
from app.rag.parsing.exceptions import (
    DocumentParsingError,
    EmptyDocumentError,
    ParserUnavailableError,
    UnsupportedDocumentFormatError,
)
from app.rag.parsing.merge import merge_structured_and_multimodal
from app.rag.parsing.router import DocumentParserRouter, get_document_parser_router

__all__ = [
    "DocumentElement",
    "DocumentParserRouter",
    "DocumentParsingError",
    "EmptyDocumentError",
    "ParsedDocument",
    "ParserUnavailableError",
    "UnsupportedDocumentFormatError",
    "get_document_parser_router",
    "merge_structured_and_multimodal",
]
