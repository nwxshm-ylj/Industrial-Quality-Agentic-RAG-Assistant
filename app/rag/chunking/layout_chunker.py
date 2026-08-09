from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable, Mapping

from app.rag.chunking.token_counter import TokenCounter, UnicodeTokenCounter
from app.rag.parsing.contracts import DocumentElement, ParsedDocument


CHUNK_STRATEGY_VERSION = "layout-token-v2"


@dataclass(frozen=True)
class LayoutChunkerConfig:
    target_tokens: int = 384
    max_tokens: int = 512
    overlap_tokens: int = 48

    def validate(self) -> None:
        if self.target_tokens < 32:
            raise ValueError("target_tokens must be at least 32")
        if self.max_tokens < self.target_tokens:
            raise ValueError("max_tokens must be greater than or equal to target_tokens")
        if self.overlap_tokens < 0 or self.overlap_tokens >= self.target_tokens:
            raise ValueError(
                "overlap_tokens must be non-negative and smaller than target_tokens"
            )


@dataclass(frozen=True)
class _Unit:
    text: str
    element_ids: tuple[str, ...]
    page_numbers: tuple[int, ...]
    bboxes: tuple[dict[str, Any], ...]
    asset_ids: tuple[str, ...]


class LayoutChunker:
    """Create retrieval chunks from parser-neutral document elements."""

    strategy_version = CHUNK_STRATEGY_VERSION

    def __init__(
        self,
        config: LayoutChunkerConfig | None = None,
        *,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self.config = config or LayoutChunkerConfig()
        self.config.validate()
        self.token_counter = token_counter or UnicodeTokenCounter()

    def split_document(self, raw_document: Mapping[str, Any]) -> list[dict]:
        document = ParsedDocument.from_mapping(raw_document)
        chunks: list[dict] = []
        text_elements: list[DocumentElement] = []
        current_heading: tuple[str, ...] | None = None

        def flush_text() -> None:
            nonlocal text_elements
            if not text_elements:
                return
            chunks.extend(self._split_text_elements(document, text_elements))
            text_elements = []

        for element in document.elements:
            if element.element_type in {"heading", "title"}:
                flush_text()
                current_heading = element.heading_path
                continue
            if element.element_type == "table":
                flush_text()
                chunks.extend(self._split_table_element(document, element))
                current_heading = None
                continue

            heading_path = element.heading_path
            if current_heading is not None and heading_path != current_heading:
                flush_text()
            current_heading = heading_path
            text_elements.append(element)

        flush_text()
        return _ensure_unique_chunk_ids(chunks)

    def _split_text_elements(
        self,
        document: ParsedDocument,
        elements: list[DocumentElement],
    ) -> list[dict]:
        heading_path = elements[0].heading_path
        content_budget = self._content_budget(heading_path)
        units = self._elements_to_units(elements, content_budget)
        return self._merge_units(
            document,
            units,
            heading_path=heading_path,
            section_type="text",
            table_index=None,
        )

    def _split_table_element(
        self,
        document: ParsedDocument,
        element: DocumentElement,
    ) -> list[dict]:
        heading_path = element.heading_path
        content_budget = self._content_budget(heading_path)
        lines = [line.strip() for line in element.text.splitlines() if line.strip()]
        base_unit = self._unit_for_text(element.text, element)
        if self.token_counter.count(element.text) <= content_budget or len(lines) < 3:
            units = self._split_unit(base_unit, content_budget)
            return [
                self._build_chunk(
                    document,
                    [unit],
                    heading_path=heading_path,
                    section_type="table",
                    table_index=element.table_index,
                )
                for unit in units
            ]

        header = lines[:2]
        rows = lines[2:]
        chunks: list[dict] = []
        current_rows: list[str] = []

        def flush_rows() -> None:
            nonlocal current_rows
            if not current_rows:
                return
            table_text = "\n".join(header + current_rows)
            for part in self._split_table_text(
                table_text,
                header=header,
                element=element,
                content_budget=content_budget,
            ):
                chunks.append(
                    self._build_chunk(
                        document,
                        [part],
                        heading_path=heading_path,
                        section_type="table",
                        table_index=element.table_index,
                    )
                )
            current_rows = []

        for row in rows:
            candidate = "\n".join(header + current_rows + [row])
            if current_rows and self.token_counter.count(candidate) > content_budget:
                flush_rows()
            current_rows.append(row)
            if self.token_counter.count("\n".join(header + current_rows)) > content_budget:
                flush_rows()
        flush_rows()
        return chunks

    def _split_table_text(
        self,
        table_text: str,
        *,
        header: list[str],
        element: DocumentElement,
        content_budget: int,
    ) -> list[_Unit]:
        unit = self._unit_for_text(table_text, element)
        if self.token_counter.count(table_text) <= content_budget:
            return [unit]

        header_text = "\n".join(header)
        remaining_budget = content_budget - self.token_counter.count(header_text) - 1
        if remaining_budget < 16:
            return self._split_unit(unit, content_budget)

        body = "\n".join(table_text.splitlines()[len(header):]).strip()
        body_lines = [line.strip() for line in body.splitlines() if line.strip()]
        if len(body_lines) == 1:
            cells = _markdown_cells(body_lines[0])
            if len(cells) >= 2:
                row_key = cells[0]
                row_value = " | ".join(cells[1:])
                row_prefix = f"| {row_key} | "
                row_budget = (
                    remaining_budget
                    - self.token_counter.count(row_prefix)
                    - 1
                )
                if row_budget >= 8:
                    return [
                        self._unit_for_text(
                            f"{header_text}\n{row_prefix}{part} |",
                            element,
                        )
                        for part in self.token_counter.split(row_value, row_budget)
                        if part.strip()
                    ]
        return [
            self._unit_for_text(f"{header_text}\n{part}", element)
            for part in self.token_counter.split(body, remaining_budget)
            if part.strip()
        ]

    def _elements_to_units(
        self,
        elements: Iterable[DocumentElement],
        content_budget: int,
    ) -> list[_Unit]:
        units: list[_Unit] = []
        for element in elements:
            units.extend(self._split_unit(self._unit_for_text(element.text, element), content_budget))
        return units

    def _split_unit(self, unit: _Unit, content_budget: int) -> list[_Unit]:
        parts = self.token_counter.split(unit.text, content_budget)
        return [
            _Unit(
                text=part,
                element_ids=unit.element_ids,
                page_numbers=unit.page_numbers,
                bboxes=unit.bboxes,
                asset_ids=unit.asset_ids,
            )
            for part in parts
        ]

    def _merge_units(
        self,
        document: ParsedDocument,
        units: list[_Unit],
        *,
        heading_path: tuple[str, ...],
        section_type: str,
        table_index: int | None,
    ) -> list[dict]:
        chunks: list[dict] = []
        current: list[_Unit] = []
        current_has_new_content = False
        target_budget = min(
            self.config.target_tokens,
            self._content_budget(heading_path),
        )
        max_budget = self._content_budget(heading_path)

        for unit in units:
            candidate = "\n\n".join(item.text for item in current + [unit])
            if current and self.token_counter.count(candidate) > max_budget:
                chunks.append(
                    self._build_chunk(
                        document,
                        current,
                        heading_path=heading_path,
                        section_type=section_type,
                        table_index=table_index,
                    )
                )
                current = self._overlap_units(current)
                current_has_new_content = False
            current.append(unit)
            current_has_new_content = True
            if self.token_counter.count("\n\n".join(item.text for item in current)) >= target_budget:
                chunks.append(
                    self._build_chunk(
                        document,
                        current,
                        heading_path=heading_path,
                        section_type=section_type,
                        table_index=table_index,
                    )
                )
                current = self._overlap_units(current)
                current_has_new_content = False

        if current and (current_has_new_content or not chunks):
            chunk = self._build_chunk(
                document,
                current,
                heading_path=heading_path,
                section_type=section_type,
                table_index=table_index,
            )
            if not chunks or chunk["metadata"]["chunk_id"] != chunks[-1]["metadata"]["chunk_id"]:
                chunks.append(chunk)
        return chunks

    def _overlap_units(self, units: list[_Unit]) -> list[_Unit]:
        budget = self.config.overlap_tokens
        if budget <= 0:
            return []
        selected: list[_Unit] = []
        used = 0
        for unit in reversed(units):
            unit_tokens = self.token_counter.count(unit.text)
            remaining = budget - used
            if remaining <= 0:
                break
            if unit_tokens <= remaining:
                selected.append(unit)
                used += unit_tokens
                continue
            tail = self.token_counter.tail(unit.text, remaining)
            if tail:
                selected.append(
                    _Unit(
                        text=tail,
                        element_ids=unit.element_ids,
                        page_numbers=unit.page_numbers,
                        bboxes=unit.bboxes,
                        asset_ids=unit.asset_ids,
                    )
                )
            break
        return list(reversed(selected))

    def _build_chunk(
        self,
        document: ParsedDocument,
        units: list[_Unit],
        *,
        heading_path: tuple[str, ...],
        section_type: str,
        table_index: int | None,
    ) -> dict:
        body = "\n\n".join(unit.text for unit in units if unit.text.strip()).strip()
        page_numbers = sorted({page for unit in units for page in unit.page_numbers})
        prefix = self._context_prefix(heading_path, page_numbers)
        text = f"{prefix}{body}" if prefix else body
        token_count = self.token_counter.count(text)
        if token_count > self.config.max_tokens:
            raise ValueError(
                f"chunk exceeds max token budget: {token_count} > {self.config.max_tokens}"
            )

        element_ids = _unique(
            element_id for unit in units for element_id in unit.element_ids
        )
        asset_ids = _unique(asset_id for unit in units for asset_id in unit.asset_ids)
        bboxes = _unique_dicts(bbox for unit in units for bbox in unit.bboxes)
        content_hash = sha256(text.encode("utf-8")).hexdigest()
        chunk_id = _stable_chunk_id(
            source=document.source,
            parser_version=document.parser_version,
            element_ids=element_ids,
            content_hash=content_hash,
        )
        page_start = page_numbers[0] if page_numbers else None
        page_end = page_numbers[-1] if page_numbers else None
        metadata = {
            "source": document.source,
            "doc_type": document.metadata.get("doc_type", ""),
            "file_ext": document.file_ext,
            "parser": document.parser_name,
            "parser_name": document.parser_name,
            "parser_version": document.parser_version,
            "chunk_strategy": self.strategy_version,
            "token_counter": self.token_counter.name,
            "token_count": token_count,
            "content_hash": content_hash,
            "chunk_id": chunk_id,
            "section_type": section_type,
            "heading_path": " > ".join(heading_path),
            "page_number": page_start,
            "page_start": page_start,
            "page_end": page_end,
            "table_index": table_index,
            "element_ids": element_ids,
            "asset_ids": asset_ids,
            "bboxes": bboxes,
        }
        return {"text": text, "metadata": metadata}

    def _content_budget(self, heading_path: tuple[str, ...]) -> int:
        heading_prefix = self._heading_prefix(heading_path)
        reserved_page_tokens = 10
        return max(
            24,
            self.config.max_tokens
            - self.token_counter.count(heading_prefix)
            - reserved_page_tokens,
        )

    def _context_prefix(
        self,
        heading_path: tuple[str, ...],
        page_numbers: list[int],
    ) -> str:
        values = []
        heading_prefix = self._heading_prefix(heading_path)
        if heading_prefix:
            values.append(heading_prefix)
        if page_numbers:
            page_value = (
                str(page_numbers[0])
                if len(page_numbers) == 1
                else f"{page_numbers[0]}-{page_numbers[-1]}"
            )
            values.append(f"[页码] {page_value}")
        return "\n".join(values) + ("\n" if values else "")

    def _heading_prefix(self, heading_path: tuple[str, ...]) -> str:
        if not heading_path:
            return ""
        heading = " > ".join(value for value in heading_path if value)
        max_heading_tokens = max(16, self.config.max_tokens // 4)
        if self.token_counter.count(heading) > max_heading_tokens:
            heading = self.token_counter.tail(heading, max_heading_tokens)
        return f"[章节] {heading}"

    @staticmethod
    def _unit_for_text(text: str, element: DocumentElement) -> _Unit:
        bboxes = ()
        if element.bbox is not None:
            bboxes = (
                {
                    "page_number": element.page_number,
                    "x0": element.bbox[0],
                    "y0": element.bbox[1],
                    "x1": element.bbox[2],
                    "y1": element.bbox[3],
                },
            )
        metadata_pages = element.metadata.get("position_pages")
        if isinstance(metadata_pages, (list, tuple)):
            page_numbers = tuple(
                int(page)
                for page in metadata_pages
                if isinstance(page, int) or str(page).isdigit()
            )
        else:
            page_numbers = ()
        if not page_numbers and element.page_number is not None:
            page_numbers = (element.page_number,)
        metadata_asset_ids = element.metadata.get("asset_ids")
        asset_ids = []
        if isinstance(metadata_asset_ids, (list, tuple, set)):
            asset_ids.extend(
                str(asset_id).strip()
                for asset_id in metadata_asset_ids
                if str(asset_id).strip()
            )
        if element.asset_id:
            asset_ids.insert(0, element.asset_id)
        return _Unit(
            text=text.strip(),
            element_ids=(element.element_id,),
            page_numbers=page_numbers,
            bboxes=bboxes,
            asset_ids=tuple(_unique(asset_ids)),
        )


def _stable_chunk_id(
    *,
    source: str,
    parser_version: str,
    element_ids: list[str],
    content_hash: str,
) -> str:
    raw = "\x1f".join([source.lower(), parser_version, *element_ids, content_hash])
    return f"chunk_{sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def scope_chunk_id(
    doc_id: str,
    base_chunk_id: str,
    *,
    operation_id: str | None = None,
) -> str:
    """Namespace a stable content chunk for one document/index operation."""

    values = [doc_id]
    if operation_id:
        values.append(operation_id)
    values.append(base_chunk_id)
    return "_".join(values)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _unique_dicts(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen = set()
    for value in values:
        key = tuple(sorted(value.items()))
        if key in seen:
            continue
        seen.add(key)
        results.append(value)
    return results


def _ensure_unique_chunk_ids(chunks: list[dict]) -> list[dict]:
    occurrences: dict[str, int] = {}
    for chunk in chunks:
        metadata = chunk["metadata"]
        base_id = str(metadata["chunk_id"])
        occurrence = occurrences.get(base_id, 0)
        occurrences[base_id] = occurrence + 1
        if occurrence:
            metadata["chunk_id"] = f"{base_id}_{occurrence + 1}"
    return chunks


def _markdown_cells(row: str) -> list[str]:
    value = row.strip().strip("|")
    return [cell.strip() for cell in value.split("|")]
