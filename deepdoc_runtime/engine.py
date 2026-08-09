from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Protocol

from deepdoc_runtime.settings import RuntimeSettings


REQUIRED_MODEL_FILES = (
    "det.onnx",
    "rec.onnx",
    "ocr.res",
    "layout.onnx",
    "tsr.onnx",
    "updown_concat_xgb.model",
)
REQUIRED_TOKENIZER_FILES = ("huqie.txt", "huqie.txt.trie")


class DeepDocEngine(Protocol):
    def parse_pdf(self, path: Path, *, zoomin: int, max_pages: int) -> Any: ...


class ReferenceDeepDocEngine:
    """Adapter around the Apache-2.0 InfiniFlow DeepDOC PDF parser."""

    def __init__(self, parser: Any) -> None:
        self.parser = parser
        self._parse_lock = Lock()

    def parse_pdf(self, path: Path, *, zoomin: int, max_pages: int) -> dict:
        # The reference parser stores page images/boxes on the instance and is
        # not thread-safe. Serialize calls while still reusing loaded models.
        with self._parse_lock:
            self.parser.__images__(
                str(path),
                zoomin,
                0,
                max_pages,
                _progress_callback,
            )
            self.parser._layouts_rec(zoomin)
            self.parser._table_transformer_job(zoomin)
            self.parser._text_merge()
            tables = self.parser._extract_table_figure(
                True,
                zoomin,
                True,
                True,
            )
            self.parser._concat_downward()
            sections = [
                (box["text"], self.parser._line_tag(box, zoomin))
                for box in self.parser.boxes
                if str(box.get("text") or "").strip()
            ]
        return {
            "sections": sections,
            "tables": [_json_safe_table(table) for table in tables],
            "metadata": {
                "runtime": "infiniflow-deepdoc",
                "engine_version": "deepdoc-http-v1",
            },
        }


def create_reference_engine() -> DeepDocEngine:
    settings = RuntimeSettings.from_environment()
    validate_runtime_resources(settings)
    source = str(settings.source_dir.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    os.environ["RAG_PROJECT_BASE"] = str(settings.resource_root.resolve())
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    module = importlib.import_module(
        "service.core.deepdoc.parser.pdf_parser"
    )
    parser_type = getattr(module, "RAGFlowPdfParser")
    return ReferenceDeepDocEngine(parser_type())


def load_engine(factory_path: str) -> DeepDocEngine:
    module_name, separator, attribute_name = factory_path.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError(
            "DEEPDOC_ENGINE_FACTORY must use module:attribute format"
        )
    factory: Callable[[], DeepDocEngine] = getattr(
        importlib.import_module(module_name),
        attribute_name,
    )
    engine = factory()
    if not hasattr(engine, "parse_pdf"):
        raise TypeError("DeepDOC engine must implement parse_pdf")
    return engine


def validate_runtime_resources(settings: RuntimeSettings) -> None:
    if not settings.source_dir.is_dir():
        raise FileNotFoundError(
            f"DeepDOC source directory does not exist: {settings.source_dir}"
        )
    parser_path = (
        settings.source_dir
        / "service/core/deepdoc/parser/pdf_parser.py"
    )
    if not parser_path.is_file():
        raise FileNotFoundError(f"DeepDOC parser source is missing: {parser_path}")
    if not settings.model_dir.is_dir():
        raise FileNotFoundError(
            f"DeepDOC model directory does not exist: {settings.model_dir}"
        )
    missing = [
        name for name in REQUIRED_MODEL_FILES
        if not (settings.model_dir / name).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "DeepDOC model files are incomplete: " + ", ".join(missing)
        )
    tokenizer_dir = settings.resource_root / "rag/res"
    missing_tokenizer_files = [
        name for name in REQUIRED_TOKENIZER_FILES
        if not (tokenizer_dir / name).is_file()
    ]
    if missing_tokenizer_files:
        raise FileNotFoundError(
            "DeepDOC tokenizer files are incomplete: "
            + ", ".join(missing_tokenizer_files)
        )


def _json_safe_table(table: Any) -> Any:
    if not isinstance(table, (list, tuple)) or len(table) != 2:
        return table
    payload, positions = table
    if not isinstance(payload, (list, tuple)) or len(payload) != 2:
        return table
    _image, rows = payload
    # Images are persisted by the main application's multimodal lifecycle.
    # The parser service returns table/figure text and positions only.
    return ((None, rows), positions)


def _progress_callback(*args: Any, **kwargs: Any) -> None:
    del args, kwargs
