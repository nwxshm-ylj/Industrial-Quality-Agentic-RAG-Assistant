from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from app.rag.parsing.contracts import DocumentElement, ParsedDocument


MULTIMODAL_PARSER_NAME = "multimodal-v1"


def merge_structured_and_multimodal(
    structured_document: Mapping[str, Any] | None,
    multimodal_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge layout elements with OCR text and page/slide asset references.

    The structured parser remains authoritative for document order, headings,
    tables and coordinates. The multimodal parser contributes asset IDs and
    OCR-only text that is not already present on the corresponding page.
    """

    if structured_document is None:
        return dict(multimodal_document)

    structured = ParsedDocument.from_mapping(structured_document)
    raw_assets = multimodal_document.get("assets") or []
    assets = [dict(asset) for asset in raw_assets if isinstance(asset, Mapping)]
    assets_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for asset in assets:
        metadata = asset.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        page_number = _optional_positive_int(metadata.get("page_number"))
        if page_number is not None:
            assets_by_page[page_number].append(asset)

    page_text: dict[int, list[str]] = defaultdict(list)
    page_heading: dict[int, tuple[str, ...]] = {}
    page_reading_order: dict[int, int] = defaultdict(int)
    merged_elements: list[DocumentElement] = []

    for index, element in enumerate(structured.elements):
        value = element.to_dict()
        pages = _element_pages(element)
        asset_ids = _asset_ids_for_pages(assets_by_page, pages)
        existing_asset_ids = _string_values(element.metadata.get("asset_ids"))
        combined_asset_ids = _unique([*existing_asset_ids, *asset_ids])
        if combined_asset_ids:
            value["asset_id"] = value.get("asset_id") or combined_asset_ids[0]
            value["asset_ids"] = combined_asset_ids

        merged = DocumentElement.from_mapping(
            value,
            source=structured.source,
            index=index,
        )
        merged_elements.append(merged)
        for page in pages:
            page_text[page].append(element.text)
            page_reading_order[page] = max(
                page_reading_order[page],
                element.reading_order or 0,
            )
            if element.heading_path:
                page_heading[page] = element.heading_path

    ocr_element_count = 0
    seen_ocr: set[tuple[int, str]] = set()
    for page_number, page_assets in sorted(assets_by_page.items()):
        normalized_page_text = _normalize_for_comparison(
            "\n".join(page_text.get(page_number, []))
        )
        for asset in page_assets:
            asset_text = str(asset.get("text") or "").strip()
            ocr_text = _supplemental_asset_text(
                asset_text,
                normalized_page_text=normalized_page_text,
            )
            normalized_ocr = _normalize_for_comparison(ocr_text)
            if not normalized_ocr:
                continue
            if normalized_ocr in normalized_page_text:
                continue
            dedupe_key = (page_number, normalized_ocr)
            if dedupe_key in seen_ocr:
                continue
            seen_ocr.add(dedupe_key)

            metadata = asset.get("metadata")
            metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
            asset_id = str(metadata.get("asset_id") or "").strip() or None
            page_reading_order[page_number] += 1
            value = {
                "text": ocr_text,
                "element_type": "ocr_text",
                "section_type": "ocr_text",
                "page_number": page_number,
                "reading_order": page_reading_order[page_number],
                "heading_path": list(page_heading.get(page_number, ())),
                "asset_id": asset_id,
                "asset_ids": [asset_id] if asset_id else [],
                "modality": metadata.get("modality"),
                "mime_type": metadata.get("mime_type"),
                "ocr_source_parser": MULTIMODAL_PARSER_NAME,
            }
            merged_elements.append(
                DocumentElement.from_mapping(
                    value,
                    source=structured.source,
                    index=len(merged_elements),
                )
            )
            page_text[page_number].append(ocr_text)
            normalized_page_text = _normalize_for_comparison(
                "\n".join(page_text[page_number])
            )
            ocr_element_count += 1

    merged_elements.sort(key=_element_sort_key)
    parser_name = f"{structured.parser_name}+{MULTIMODAL_PARSER_NAME}"
    parser_version = f"{structured.parser_version}+{MULTIMODAL_PARSER_NAME}"
    metadata = {
        **dict(structured.metadata),
        "parser_components": [structured.parser_name, MULTIMODAL_PARSER_NAME],
        "multimodal_parser": MULTIMODAL_PARSER_NAME,
        "multimodal_asset_count": len(assets),
        "ocr_element_count": ocr_element_count,
        "multimodal_merged": True,
    }
    asset_dir = multimodal_document.get("asset_dir")
    if asset_dir:
        metadata["asset_dir"] = str(asset_dir)

    result = ParsedDocument(
        source=structured.source,
        content="\n\n".join(
            element.text for element in merged_elements if element.text.strip()
        ),
        file_ext=structured.file_ext,
        elements=tuple(merged_elements),
        parser_name=parser_name,
        parser_version=parser_version,
        assets=tuple(assets),
        metadata=metadata,
    )
    return result.to_dict()


def _element_pages(element: DocumentElement) -> list[int]:
    pages = []
    raw_pages = element.metadata.get("position_pages")
    if isinstance(raw_pages, Iterable) and not isinstance(raw_pages, (str, bytes)):
        pages.extend(
            page
            for page in (_optional_positive_int(value) for value in raw_pages)
            if page is not None
        )
    if element.page_number is not None:
        pages.append(element.page_number)
    return _unique(pages)


def _asset_ids_for_pages(
    assets_by_page: Mapping[int, list[dict[str, Any]]],
    pages: Iterable[int],
) -> list[str]:
    values = []
    for page in pages:
        for asset in assets_by_page.get(page, []):
            metadata = asset.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            asset_id = str(metadata.get("asset_id") or "").strip()
            if asset_id:
                values.append(asset_id)
    return _unique(values)


def _supplemental_asset_text(
    value: str,
    *,
    normalized_page_text: str,
) -> str:
    marker = "[OCR]"
    if marker in value:
        return value.split(marker, 1)[1].strip()
    if not normalized_page_text:
        return value.strip()
    novel_lines = []
    for line in value.splitlines():
        cleaned = line.strip()
        normalized_line = _normalize_for_comparison(cleaned)
        if cleaned and normalized_line and normalized_line not in normalized_page_text:
            novel_lines.append(cleaned)
    return "\n".join(novel_lines)


def _normalize_for_comparison(value: str) -> str:
    return "".join(value.lower().split())


def _element_sort_key(element: DocumentElement) -> tuple[Any, ...]:
    bbox = element.bbox or (float("inf"), float("inf"), 0.0, 0.0)
    return (
        element.page_number or 10**9,
        element.reading_order or 10**9,
        bbox[1],
        bbox[0],
    )


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _unique(values: Iterable[Any]) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
