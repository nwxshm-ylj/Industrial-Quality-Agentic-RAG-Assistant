from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSettings:
    source_dir: Path
    resource_root: Path
    model_dir: Path
    engine_factory: str
    max_file_bytes: int
    default_zoomin: int
    max_pages: int

    @classmethod
    def from_environment(cls) -> "RuntimeSettings":
        source_dir = Path(
            os.getenv("DEEPDOC_SOURCE_DIR", "/opt/deepdoc_source")
        )
        resource_root = Path(
            os.getenv("DEEPDOC_RESOURCE_ROOT", "/opt/runtime_resources")
        )
        model_dir = Path(
            os.getenv(
                "DEEPDOC_MODEL_DIR",
                str(resource_root / "rag/res/deepdoc"),
            )
        )
        return cls(
            source_dir=source_dir,
            resource_root=resource_root,
            model_dir=model_dir,
            engine_factory=os.getenv(
                "DEEPDOC_ENGINE_FACTORY",
                "deepdoc_runtime.engine:create_reference_engine",
            ),
            max_file_bytes=_positive_int(
                "DEEPDOC_MAX_FILE_BYTES", 100 * 1024 * 1024
            ),
            default_zoomin=_positive_int("DEEPDOC_ZOOMIN", 3),
            max_pages=_positive_int("DEEPDOC_MAX_PAGES", 2000),
        )


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value
