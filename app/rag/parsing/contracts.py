from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence


_ELEMENT_KEYS = {
    "element_id",
    "element_type",
    "section_type",
    "text",
    "page_number",
    "bbox",
    "reading_order",
    "heading_path",
    "heading_level",
    "table_index",
    "asset_id",
    "confidence",
}

_DOCUMENT_KEYS = {
    "source",
    "content",
    "file_ext",
    "sections",
    "elements",
    "parser",
    "parser_name",
    "parser_version",
    "assets",
    "metadata",
}


@dataclass(frozen=True)
class DocumentElement:
    """Normalized layout element emitted by every document parser."""

    element_id: str
    element_type: str
    text: str
    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    reading_order: int | None = None
    heading_path: tuple[str, ...] = ()
    heading_level: int | None = None
    table_index: int | None = None
    asset_id: str | None = None
    confidence: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        source: str,
        index: int,
    ) -> "DocumentElement":
        text = str(value.get("text", "")).strip()
        element_type = str(
            value.get("element_type") or value.get("section_type") or "paragraph"
        )
        page_number = _optional_int(value.get("page_number"))
        bbox = _normalize_bbox(value.get("bbox"))
        heading_path = _normalize_heading_path(value.get("heading_path"))
        element_id = str(value.get("element_id") or "").strip()
        if not element_id:
            element_id = _build_element_id(
                source=source,
                index=index,
                element_type=element_type,
                page_number=page_number,
                text=text,
            )

        metadata = {
            key: item
            for key, item in value.items()
            if key not in _ELEMENT_KEYS
        }
        return cls(
            element_id=element_id,
            element_type=element_type,
            text=text,
            page_number=page_number,
            bbox=bbox,
            reading_order=_optional_int(value.get("reading_order")),
            heading_path=heading_path,
            heading_level=_optional_int(value.get("heading_level")),
            table_index=_optional_int(value.get("table_index")),
            asset_id=_optional_str(value.get("asset_id")),
            confidence=_optional_float(value.get("confidence")),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.metadata)
        result.update(
            {
                "element_id": self.element_id,
                "element_type": self.element_type,
                # Keep the current splitter and document service contract.
                "section_type": self.element_type,
                "text": self.text,
                "page_number": self.page_number,
                "bbox": list(self.bbox) if self.bbox is not None else None,
                "reading_order": self.reading_order,
                "heading_path": list(self.heading_path),
                "heading_level": self.heading_level,
                "table_index": self.table_index,
                "asset_id": self.asset_id,
                "confidence": self.confidence,
            }
        )
        return result


@dataclass(frozen=True)
class ParsedDocument:
    """Parser-neutral representation used before chunk generation."""

    source: str
    content: str
    file_ext: str
    elements: tuple[DocumentElement, ...]
    parser_name: str
    parser_version: str
    assets: tuple[dict[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ParsedDocument":
        source = str(value.get("source", "")).strip()
        file_ext = str(value.get("file_ext", "")).lower().strip()
        parser_name = str(
            value.get("parser_name") or value.get("parser") or "unknown"
        ).strip()
        parser_version = str(
            value.get("parser_version") or value.get("parser") or parser_name
        ).strip()
        raw_elements = value.get("elements") or value.get("sections") or []
        elements = tuple(
            DocumentElement.from_mapping(item, source=source, index=index)
            for index, item in enumerate(raw_elements)
            if isinstance(item, Mapping) and str(item.get("text", "")).strip()
        )
        content = str(value.get("content", "")).strip()
        if not content and elements:
            content = "\n\n".join(element.text for element in elements).strip()

        explicit_metadata = value.get("metadata")
        metadata = dict(explicit_metadata) if isinstance(explicit_metadata, Mapping) else {}
        metadata.update(
            {
                key: item
                for key, item in value.items()
                if key not in _DOCUMENT_KEYS
            }
        )
        raw_assets = value.get("assets") or []
        assets = tuple(dict(item) for item in raw_assets if isinstance(item, Mapping))
        return cls(
            source=source,
            content=content,
            file_ext=file_ext,
            elements=elements,
            parser_name=parser_name,
            parser_version=parser_version,
            assets=assets,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        elements = [element.to_dict() for element in self.elements]
        result = dict(self.metadata)
        result.update(
            {
                "source": self.source,
                "content": self.content,
                "file_ext": self.file_ext,
                # ``sections`` is the legacy contract; ``elements`` is the V2 contract.
                "sections": [dict(element) for element in elements],
                "elements": elements,
                "parser": self.parser_name,
                "parser_name": self.parser_name,
                "parser_version": self.parser_version,
                "metadata": dict(self.metadata),
            }
        )
        if self.assets:
            result["assets"] = [dict(asset) for asset in self.assets]
        return result


def _build_element_id(
    *,
    source: str,
    index: int,
    element_type: str,
    page_number: int | None,
    text: str,
) -> str:
    normalized_source = Path(source).name.lower()
    raw = "\x1f".join(
        [
            normalized_source,
            str(index),
            element_type,
            str(page_number or ""),
            " ".join(text.split()),
        ]
    )
    return f"element_{sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _normalize_heading_path(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(">") if part.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()


def _normalize_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    if len(value) != 4:
        return None
    try:
        return tuple(float(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
