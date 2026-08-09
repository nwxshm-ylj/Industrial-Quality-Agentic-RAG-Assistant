from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.rag.parsing.base import DocumentParser
from app.rag.parsing.contracts import ParsedDocument
from app.rag.parsing.deepdoc_adapter import (
    DeepDocParserAdapter,
    build_runtime_loader,
)
from app.rag.parsing.exceptions import (
    DocumentParsingError,
    ParserUnavailableError,
    UnsupportedDocumentFormatError,
)
from app.rag.parsing.native_adapter import NativeStructuredParser


class DocumentParserRouter:
    """Selects a parser without exposing parser-specific implementations."""

    def __init__(self, parsers: tuple[DocumentParser, ...] | None = None) -> None:
        self._parsers: dict[str, DocumentParser] = {}
        self._defaults: dict[str, str] = {}
        for parser in parsers or ():
            self.register(parser, make_default=True)

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset(self._defaults)

    def register(self, parser: DocumentParser, *, make_default: bool = False) -> None:
        if parser.name in self._parsers:
            raise ValueError(f"解析器已注册: {parser.name}")
        self._parsers[parser.name] = parser
        for extension in parser.supported_extensions:
            normalized = _normalize_extension(extension)
            if make_default or normalized not in self._defaults:
                self._defaults[normalized] = parser.name

    def parse(
        self,
        path: Path,
        *,
        parser_name: str | None = None,
        fallback_parser_name: str | None = None,
    ) -> ParsedDocument:
        extension = _normalize_extension(path.suffix)
        selected_name = parser_name or self._defaults.get(extension)
        parser = self._parsers.get(selected_name or "")
        if extension not in self.supported_extensions:
            supported = ", ".join(sorted(self.supported_extensions))
            raise UnsupportedDocumentFormatError(
                f"不支持的文档格式: {extension or '无扩展名'}。支持格式: {supported}"
            )
        if parser is None or extension not in parser.supported_extensions:
            raise ParserUnavailableError(f"解析器不可用: {parser_name}")
        try:
            return parser.parse(path)
        except DocumentParsingError as exc:
            fallback = self._parsers.get(fallback_parser_name or "")
            if (
                fallback is None
                or fallback.name == parser.name
                or extension not in fallback.supported_extensions
            ):
                raise
            result = fallback.parse(path)
            _log_parser_fallback(
                path=path,
                parser_name=parser.name,
                fallback_parser_name=fallback.name,
                error=exc,
            )
            return ParsedDocument(
                source=result.source,
                content=result.content,
                file_ext=result.file_ext,
                elements=result.elements,
                parser_name=result.parser_name,
                parser_version=result.parser_version,
                assets=result.assets,
                metadata={
                    **dict(result.metadata),
                    "parser_fallback_from": parser.name,
                    "parser_fallback_reason": str(exc),
                },
            )


@lru_cache(maxsize=8)
def get_document_parser_router(
    *,
    deepdoc_enabled: bool = False,
    deepdoc_runtime_factory: str | None = None,
    deepdoc_model_dir: str | None = None,
    deepdoc_require_model_files: bool = True,
    deepdoc_zoomin: int = 3,
    deepdoc_max_pages: int = 2000,
) -> DocumentParserRouter:
    """Return the process-wide parser registry used by document ingestion."""

    router = DocumentParserRouter((NativeStructuredParser(),))
    if deepdoc_enabled:
        runtime_loader = (
            build_runtime_loader(deepdoc_runtime_factory)
            if deepdoc_runtime_factory
            else _missing_deepdoc_runtime_loader
        )
        router.register(
            DeepDocParserAdapter(
                runtime_loader,
                model_dir=deepdoc_model_dir,
                require_model_files=deepdoc_require_model_files,
                zoomin=deepdoc_zoomin,
                max_pages=deepdoc_max_pages,
            )
        )
    return router


def _normalize_extension(extension: str) -> str:
    normalized = extension.lower().strip()
    if normalized and not normalized.startswith("."):
        normalized = f".{normalized}"
    return normalized


def _missing_deepdoc_runtime_loader() -> Any:
    raise ParserUnavailableError("未配置 DEEPDOC_RUNTIME_FACTORY")


def _log_parser_fallback(
    *,
    path: Path,
    parser_name: str,
    fallback_parser_name: str,
    error: Exception,
) -> None:
    fields = {
        "filename": path.name,
        "parser_name": parser_name,
        "fallback_parser_name": fallback_parser_name,
        "status": "degraded",
        "error_message": str(error),
    }
    try:
        from app.core.logger import log_business_event

        log_business_event("document_parser_fallback", **fields)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "document_parser_fallback filename=%s parser=%s fallback=%s error=%s",
            path.name,
            parser_name,
            fallback_parser_name,
            error,
        )
