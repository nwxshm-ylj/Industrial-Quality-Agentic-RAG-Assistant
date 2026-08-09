from __future__ import annotations

import importlib
import logging
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from app.rag.parsing.contracts import DocumentElement, ParsedDocument
from app.rag.parsing.exceptions import (
    DocumentParsingError,
    EmptyDocumentError,
    ParserUnavailableError,
)


DEEPDOC_PARSER_NAME = "deepdoc"
DEEPDOC_PARSER_VERSION = "deepdoc-layout-v1"
_POSITION_TAG = re.compile(
    r"@@(?P<pages>[0-9-]+)\t"
    r"(?P<left>-?[0-9.]+)\t(?P<right>-?[0-9.]+)\t"
    r"(?P<top>-?[0-9.]+)\t(?P<bottom>-?[0-9.]+)##"
)
_REQUIRED_MODEL_FILES = (
    "det.onnx",
    "rec.onnx",
    "ocr.res",
    "layout.onnx",
    "tsr.onnx",
    "updown_concat_xgb.model",
)


class DeepDocRuntime(Protocol):
    def parse_pdf(
        self,
        path: Path,
        *,
        zoomin: int,
        max_pages: int,
    ) -> Any:
        ...


class DeepDocParserAdapter:
    """Normalize an optional DeepDOC runtime into the project parser contract."""

    name = DEEPDOC_PARSER_NAME
    version = DEEPDOC_PARSER_VERSION
    supported_extensions = frozenset({".pdf"})

    def __init__(
        self,
        runtime_loader: Callable[[], DeepDocRuntime],
        *,
        model_dir: str | Path | None = None,
        require_model_files: bool = True,
        zoomin: int = 3,
        max_pages: int = 2000,
    ) -> None:
        if zoomin < 1:
            raise ValueError("DeepDOC zoomin must be positive")
        if max_pages < 1:
            raise ValueError("DeepDOC max_pages must be positive")
        self._runtime_loader = runtime_loader
        self._runtime: DeepDocRuntime | None = None
        self._runtime_lock = Lock()
        self.model_dir = Path(model_dir) if model_dir else None
        self.require_model_files = require_model_files
        self.zoomin = zoomin
        self.max_pages = max_pages

    def parse(self, path: Path) -> ParsedDocument:
        started_at = perf_counter()
        if path.suffix.lower() != ".pdf":
            raise DocumentParsingError(
                f"DeepDOC 仅支持 PDF: {path.name}"
            )
        try:
            raw_result = self.runtime.parse_pdf(
                path,
                zoomin=self.zoomin,
                max_pages=self.max_pages,
            )
            elements, runtime_metadata = normalize_deepdoc_result(
                raw_result,
                source=path.name,
            )
            if not elements:
                raise EmptyDocumentError(
                    f"DeepDOC 未提取到有效内容: {path.name}"
                )
        except DocumentParsingError as exc:
            _log_deepdoc_event(
                "deepdoc_parse_failed",
                filename=path.name,
                status="failed",
                latency_ms=(perf_counter() - started_at) * 1000,
                error_message=str(exc),
            )
            raise
        except Exception as exc:
            error = DocumentParsingError(
                f"DeepDOC 解析失败: {path.name}: {exc}"
            )
            _log_deepdoc_event(
                "deepdoc_parse_failed",
                filename=path.name,
                status="failed",
                latency_ms=(perf_counter() - started_at) * 1000,
                error_message=str(error),
            )
            raise error from exc

        content = "\n\n".join(element.text for element in elements).strip()
        element_counts = Counter(element.element_type for element in elements)
        metadata = {
            "deepdoc_zoomin": self.zoomin,
            "deepdoc_max_pages": self.max_pages,
            "element_counts": dict(element_counts),
            **runtime_metadata,
        }
        result = ParsedDocument(
            source=path.name,
            content=content,
            file_ext=".pdf",
            elements=tuple(elements),
            parser_name=self.name,
            parser_version=self.version,
            metadata=metadata,
        )
        _log_deepdoc_event(
            "deepdoc_parse_completed",
            filename=path.name,
            status="success",
            latency_ms=(perf_counter() - started_at) * 1000,
            element_count=len(elements),
            table_count=element_counts.get("table", 0),
        )
        return result

    @property
    def runtime(self) -> DeepDocRuntime:
        if self._runtime is not None:
            return self._runtime
        with self._runtime_lock:
            if self._runtime is not None:
                return self._runtime
            self._validate_model_dir()
            try:
                runtime = self._runtime_loader()
            except Exception as exc:
                raise ParserUnavailableError(
                    f"DeepDOC Runtime 加载失败: {exc}"
                ) from exc
            if not hasattr(runtime, "parse_pdf"):
                raise ParserUnavailableError(
                    "DeepDOC Runtime 必须实现 parse_pdf(path, zoomin, max_pages)"
                )
            self._runtime = runtime
            return runtime

    def _validate_model_dir(self) -> None:
        if not self.require_model_files:
            return
        if self.model_dir is None:
            raise ParserUnavailableError("未配置 DEEPDOC_MODEL_DIR")
        if not self.model_dir.exists() or not self.model_dir.is_dir():
            raise ParserUnavailableError(
                f"DeepDOC 模型目录不存在: {self.model_dir}"
            )
        missing = [
            filename
            for filename in _REQUIRED_MODEL_FILES
            if not (self.model_dir / filename).is_file()
        ]
        if missing:
            raise ParserUnavailableError(
                "DeepDOC 模型文件不完整: " + ", ".join(missing)
            )


class ReferenceDeepDocRuntime:
    """Bridge for the callable style used by the FinInsRAG/RAGFlow parser."""

    def __init__(self, parser: Any) -> None:
        if not callable(parser):
            raise ParserUnavailableError("DeepDOC parser instance is not callable")
        self.parser = parser

    def parse_pdf(
        self,
        path: Path,
        *,
        zoomin: int,
        max_pages: int,
    ) -> Any:
        return self.parser(
            str(path),
            from_page=0,
            to_page=max_pages,
            zoomin=zoomin,
            callback=_noop_callback,
        )


def build_runtime_loader(factory_path: str) -> Callable[[], DeepDocRuntime]:
    """Build a lazy loader from ``module:attribute`` without changing sys.path."""

    normalized = (factory_path or "").strip()
    if ":" not in normalized:
        raise ValueError(
            "DEEPDOC_RUNTIME_FACTORY 必须使用 module:attribute 格式"
        )
    module_name, attribute_name = normalized.split(":", 1)
    if not module_name or not attribute_name:
        raise ValueError(
            "DEEPDOC_RUNTIME_FACTORY 必须使用 module:attribute 格式"
        )

    def load() -> DeepDocRuntime:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute_name)
        runtime_or_parser = factory()
        if hasattr(runtime_or_parser, "parse_pdf"):
            return runtime_or_parser
        return ReferenceDeepDocRuntime(runtime_or_parser)

    return load


def normalize_deepdoc_result(
    raw_result: Any,
    *,
    source: str,
) -> tuple[list[DocumentElement], dict[str, Any]]:
    sections, tables, metadata = _unpack_result(raw_result)
    raw_elements: list[dict[str, Any]] = []

    for index, section in enumerate(sections):
        value = _normalize_section(section, index=index)
        if value is None:
            continue
        raw_elements.append(value)

    for table_index, table in enumerate(tables, start=1):
        value = _normalize_table(table, table_index=table_index)
        if value is None:
            continue
        raw_elements.append(value)

    raw_elements.sort(
        key=lambda item: (
            item.get("page_number") or 10**9,
            item.get("bbox", [0, 10**9, 0, 0])[1]
            if item.get("bbox")
            else 10**9,
            item.get("bbox", [10**9, 0, 0, 0])[0]
            if item.get("bbox")
            else 10**9,
            item.get("reading_order") or 10**9,
        )
    )
    heading_path: list[str] = []
    for item in raw_elements:
        if item["element_type"] in {"title", "heading"}:
            heading_path = _update_heading_path(
                heading_path,
                int(item.get("heading_level") or 1),
                item["text"],
            )
        item["heading_path"] = item.get("heading_path") or list(heading_path)
    elements = [
        DocumentElement.from_mapping(item, source=source, index=index)
        for index, item in enumerate(raw_elements)
        if item.get("text", "").strip()
    ]
    return elements, metadata


def _unpack_result(raw_result: Any) -> tuple[list[Any], list[Any], dict[str, Any]]:
    if isinstance(raw_result, Mapping):
        sections = raw_result.get("elements") or raw_result.get("sections") or []
        tables = raw_result.get("tables") or []
        metadata = raw_result.get("metadata") or {}
        return list(sections), list(tables), dict(metadata)
    if isinstance(raw_result, Sequence) and not isinstance(raw_result, (str, bytes)):
        if len(raw_result) == 2:
            return list(raw_result[0] or []), list(raw_result[1] or []), {}
    raise DocumentParsingError("DeepDOC Runtime 返回了无法识别的数据结构")


def _normalize_section(section: Any, *, index: int) -> dict[str, Any] | None:
    if isinstance(section, Mapping):
        text = _clean_text(section.get("text", ""))
        if not text:
            return None
        element_type = _normalize_element_type(
            section.get("element_type")
            or section.get("layout_type")
            or section.get("section_type")
            or "paragraph"
        )
        if element_type in {"header", "footer", "page_number"}:
            return None
        bbox = _mapping_bbox(section)
        page_number = _optional_int(section.get("page_number"))
        return {
            **dict(section),
            "text": text,
            "element_type": element_type,
            "section_type": element_type,
            "page_number": page_number,
            "bbox": bbox,
            "reading_order": _optional_int(section.get("reading_order")) or index + 1,
        }

    if isinstance(section, Sequence) and not isinstance(section, (str, bytes)):
        text = _clean_text(section[0] if section else "")
        if not text:
            return None
        position = section[1] if len(section) > 1 else None
        page_number, bbox, pages = _parse_position(position)
        return {
            "text": text,
            "element_type": "paragraph",
            "section_type": "paragraph",
            "page_number": page_number,
            "bbox": bbox,
            "reading_order": index + 1,
            "position_pages": pages,
        }

    text = _clean_text(section)
    if not text:
        return None
    return {
        "text": text,
        "element_type": "paragraph",
        "section_type": "paragraph",
        "reading_order": index + 1,
    }


def _normalize_table(table: Any, *, table_index: int) -> dict[str, Any] | None:
    position = None
    payload = table
    if isinstance(table, Sequence) and not isinstance(table, (str, bytes)):
        if len(table) == 2:
            payload, position = table

    image = None
    rows = payload
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        if len(payload) == 2:
            image, rows = payload
    element_type = _visual_element_type(rows)
    text = (
        _figure_caption_text(rows)
        if element_type == "figure_caption"
        else _table_text(rows)
    )
    if not text:
        return None
    page_number, bbox, pages = _parse_position(position)
    return {
        "text": text,
        "element_type": element_type,
        "section_type": element_type,
        "page_number": page_number,
        "bbox": bbox,
        "reading_order": 100000 + table_index,
        "table_index": table_index if element_type == "table" else None,
        "position_pages": pages,
        "has_image": image is not None,
    }


def _visual_element_type(rows: Any) -> str:
    if isinstance(rows, str):
        return "table" if "<table" in rows.lower() else "figure_caption"
    if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
        if rows and all(isinstance(row, str) for row in rows):
            return "figure_caption"
    return "table"


def _figure_caption_text(value: Any) -> str:
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, Iterable):
        return "\n".join(
            text
            for text in (_clean_text(item) for item in value)
            if text
        )
    return _clean_text(value)


def _parse_position(
    value: Any,
) -> tuple[int | None, list[float] | None, list[int]]:
    if not value:
        return None, None, []
    if isinstance(value, str):
        match = _POSITION_TAG.search(value)
        if not match:
            return None, None, []
        pages = [int(page) for page in match.group("pages").split("-") if page]
        bbox = [
            float(match.group("left")),
            float(match.group("top")),
            float(match.group("right")),
            float(match.group("bottom")),
        ]
        return (pages[0] if pages else None), bbox, pages
    if isinstance(value, Sequence) and value:
        if len(value) >= 5 and isinstance(value[0], Sequence):
            pages_value, left, right, top, bottom = value[:5]
            pages = [int(page) + 1 for page in pages_value]
            return (
                pages[0] if pages else None,
                [float(left), float(top), float(right), float(bottom)],
                pages,
            )
        first = value[0]
        if isinstance(first, Sequence) and len(first) >= 5:
            pages_value, left, right, top, bottom = first[:5]
            pages = [int(page) + 1 for page in pages_value]
            return (
                pages[0] if pages else None,
                [float(left), float(top), float(right), float(bottom)],
                pages,
            )
    return None, None, []


def _mapping_bbox(value: Mapping[str, Any]) -> list[float] | None:
    bbox = value.get("bbox")
    if isinstance(bbox, Sequence) and not isinstance(bbox, (str, bytes)) and len(bbox) == 4:
        return [float(item) for item in bbox]
    keys = ("x0", "top", "x1", "bottom")
    if all(value.get(key) is not None for key in keys):
        return [float(value[key]) for key in keys]
    return None


def _table_text(rows: Any) -> str:
    if isinstance(rows, str):
        if "<table" in rows.lower():
            parser = _TableHtmlParser()
            parser.feed(rows)
            return _rows_to_markdown(parser.rows)
        return _clean_text(rows)
    if not isinstance(rows, Iterable):
        return _clean_text(rows)
    values: list[list[str]] = []
    for row in rows:
        if isinstance(row, str):
            cells = [_clean_text(row)]
        elif isinstance(row, Iterable):
            cells = [_clean_text(cell) for cell in row]
        else:
            cells = [_clean_text(row)]
        if any(cells):
            values.append(cells)
    return _rows_to_markdown(values)


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    body = normalized[1:]
    if len(normalized) == 1:
        header = ["表格内容" for _ in range(width)]
        body = normalized
    result = [
        "| " + " | ".join(_escape_markdown_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    result.extend(
        "| " + " | ".join(_escape_markdown_cell(cell) for cell in row) + " |"
        for row in body
    )
    return "\n".join(result)


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


class _TableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._colspan = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized == "tr":
            self._row = []
        elif normalized in {"td", "th"} and self._row is not None:
            self._cell_parts = []
            attr_values = dict(attrs)
            try:
                self._colspan = max(1, int(attr_values.get("colspan") or 1))
            except (TypeError, ValueError):
                self._colspan = 1
        elif normalized == "br" and self._cell_parts is not None:
            self._cell_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in {"td", "th"} and self._row is not None and self._cell_parts is not None:
            value = _clean_text("".join(self._cell_parts))
            self._row.extend([value] * self._colspan)
            self._cell_parts = None
            self._colspan = 1
        elif normalized == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None


def _normalize_element_type(value: Any) -> str:
    normalized = str(value or "paragraph").strip().lower().replace("_", " ")
    return {
        "text": "paragraph",
        "figure caption": "figure_caption",
        "table caption": "table_caption",
    }.get(normalized, normalized.replace(" ", "_"))


def _clean_text(value: Any) -> str:
    text = _POSITION_TAG.sub("", str(value or ""))
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _update_heading_path(current: list[str], level: int, title: str) -> list[str]:
    level = max(1, min(level, 6))
    result = list(current[: level - 1])
    while len(result) < level - 1:
        result.append("")
    result.append(title)
    return [value for value in result if value]


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _noop_callback(*args: Any, **kwargs: Any) -> None:
    del args, kwargs


def _log_deepdoc_event(action: str, **fields: Any) -> None:
    """Use project structured logging without making it a parser dependency."""

    try:
        from app.core.logger import log_business_event

        log_business_event(action, parser_name=DEEPDOC_PARSER_NAME, **fields)
    except Exception:
        logging.getLogger(__name__).log(
            logging.ERROR if fields.get("status") == "failed" else logging.INFO,
            "%s filename=%s status=%s latency_ms=%s error=%s",
            action,
            fields.get("filename"),
            fields.get("status"),
            fields.get("latency_ms"),
            fields.get("error_message"),
        )
