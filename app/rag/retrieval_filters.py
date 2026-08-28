from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def merge_retrieval_filter_mappings(
    explicit_filters: Mapping[str, Any] | None,
    inferred_filters: Mapping[str, Any] | None,
) -> dict[str, list[str]] | None:
    """Add inferred constraints without weakening explicit caller filters."""
    merged: dict[str, list[str]] = {
        key: list(values) if not isinstance(values, str) else [values]
        for key, values in (explicit_filters or {}).items()
        if values
    }
    for key, values in (inferred_filters or {}).items():
        if key not in merged and values:
            merged[key] = list(values) if not isinstance(values, str) else [values]
    return merged or None


@dataclass(frozen=True)
class RetrievalFilter:
    """Backend-neutral metadata filters for online retrieval."""

    doc_ids: tuple[str, ...] = ()
    doc_types: tuple[str, ...] = ()
    versions: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    vehicle_models: tuple[str, ...] = ()
    systems: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    processes: tuple[str, ...] = ()
    stations: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    symptoms: tuple[str, ...] = ()

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
            vehicle_models=normalize("vehicle_models"),
            systems=normalize("systems"),
            components=normalize("components"),
            processes=normalize("processes"),
            stations=normalize("stations"),
            failure_modes=normalize("failure_modes"),
            symptoms=normalize("symptoms"),
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
                self.vehicle_models,
                self.systems,
                self.components,
                self.processes,
                self.stations,
                self.failure_modes,
                self.symptoms,
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
                "vehicle_models": self.vehicle_models,
                "systems": self.systems,
                "components": self.components,
                "processes": self.processes,
                "stations": self.stations,
                "failure_modes": self.failure_modes,
                "symptoms": self.symptoms,
            }.items()
            if value
        }
