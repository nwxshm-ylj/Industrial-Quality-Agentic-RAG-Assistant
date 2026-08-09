from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.rag.parsing.contracts import ParsedDocument


@runtime_checkable
class DocumentParser(Protocol):
    """Internal parser interface. SDK-specific types must not cross this boundary."""

    name: str
    version: str
    supported_extensions: frozenset[str]

    def parse(self, path: Path) -> ParsedDocument:
        ...
