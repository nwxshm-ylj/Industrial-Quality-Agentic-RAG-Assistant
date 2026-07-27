from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RetrievalFilter:
    """Backend-neutral metadata filters for online retrieval."""

    doc_ids: tuple[str, ...] = ()
    doc_types: tuple[str, ...] = ()
    versions: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any] | None,
    ) -> "RetrievalFilter | None":
        if not value:
            return None

        def normalize(field: str) -> tuple[str, ...]:
            raw = value.get(field) or []
            if isinstance(raw, str):
                raw = [raw]
            normalized = tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in raw
                    if str(item).strip()
                )
            )
            if len(normalized) > 50:
                raise ValueError(
                    f"retrieval filter {field} cannot contain more than 50 values"
                )
            return normalized

        result = cls(
            doc_ids=normalize("doc_ids"),
            doc_types=normalize("doc_types"),
            versions=normalize("versions"),
            sources=normalize("sources"),
        )
        return result if result.is_active else None

    @property
    def is_active(self) -> bool:
        return any(
            (
                self.doc_ids,
                self.doc_types,
                self.versions,
                self.sources,
            )
        )

    def as_dict(self) -> dict[str, list[str]]:
        return {
            key: list(value)
            for key, value in {
                "doc_ids": self.doc_ids,
                "doc_types": self.doc_types,
                "versions": self.versions,
                "sources": self.sources,
            }.items()
            if value
        }
