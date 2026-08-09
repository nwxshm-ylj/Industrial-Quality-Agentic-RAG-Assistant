from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DEFAULT_CODE_DESTINATION = Path("data/deepdoc_runtime/source")
DEFAULT_RESOURCE_DESTINATION = Path("data/models/deepdoc-runtime-res")

SOURCE_FILES = (
    "deepdoc/__init__.py",
    "deepdoc/parser/pdf_parser.py",
    "deepdoc/vision/__init__.py",
    "deepdoc/vision/layout_recognizer.py",
    "deepdoc/vision/ocr.py",
    "deepdoc/vision/operators.py",
    "deepdoc/vision/postprocess.py",
    "deepdoc/vision/recognizer.py",
    "deepdoc/vision/table_structure_recognizer.py",
    "api/utils/file_utils.py",
    "rag/nlp/rag_tokenizer.py",
)

MODEL_FILES = (
    "det.onnx",
    "rec.onnx",
    "ocr.res",
    "layout.onnx",
    "tsr.onnx",
    "updown_concat_xgb.model",
)

PACKAGE_INITIALIZERS = (
    "service/__init__.py",
    "service/core/__init__.py",
    "service/core/api/__init__.py",
    "service/core/api/utils/__init__.py",
    "service/core/rag/__init__.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare an ignored, local DeepDOC runtime bundle from an "
            "authorized InfiniFlow/FinInsRAG source checkout."
        )
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Path ending in service/core and containing deepdoc/, rag/ and api/.",
    )
    parser.add_argument(
        "--code-destination",
        type=Path,
        default=DEFAULT_CODE_DESTINATION,
    )
    parser.add_argument(
        "--resource-destination",
        type=Path,
        default=DEFAULT_RESOURCE_DESTINATION,
    )
    args = parser.parse_args()
    prepare_runtime(
        source_root=args.source_root,
        code_destination=args.code_destination,
        resource_destination=args.resource_destination,
    )


def prepare_runtime(
    *,
    source_root: Path,
    code_destination: Path,
    resource_destination: Path,
) -> None:
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"DeepDOC source root does not exist: {source_root}")
    for relative_path in SOURCE_FILES:
        source = source_root / relative_path
        if not source.is_file():
            raise FileNotFoundError(f"Required DeepDOC source is missing: {source}")

    model_source = source_root / "rag/res/deepdoc"
    huqie_source = source_root / "rag/res"
    for filename in MODEL_FILES:
        path = model_source / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required DeepDOC model is missing: {path}")
    for filename in ("huqie.txt", "huqie.txt.trie"):
        path = huqie_source / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required tokenizer resource is missing: {path}")

    package_root = code_destination / "service/core"
    for relative_path in SOURCE_FILES:
        source = source_root / relative_path
        destination = package_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    for relative_path in PACKAGE_INITIALIZERS:
        path = code_destination / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

    parser_init = package_root / "deepdoc/parser/__init__.py"
    parser_init.write_text(
        "from .pdf_parser import RAGFlowPdfParser, PlainParser\n"
        "\n__all__ = ['RAGFlowPdfParser', 'PlainParser']\n",
        encoding="utf-8",
    )
    nlp_init = package_root / "rag/nlp/__init__.py"
    nlp_init.write_text(
        "from . import rag_tokenizer\n\n__all__ = ['rag_tokenizer']\n",
        encoding="utf-8",
    )

    deepdoc_destination = resource_destination / "deepdoc"
    deepdoc_destination.mkdir(parents=True, exist_ok=True)
    for filename in MODEL_FILES:
        shutil.copy2(model_source / filename, deepdoc_destination / filename)
    for filename in ("huqie.txt", "huqie.txt.trie"):
        shutil.copy2(huqie_source / filename, resource_destination / filename)

    notice = code_destination / "PREPARED_SOURCE_NOTICE.txt"
    notice.write_text(
        "Prepared from an authorized InfiniFlow DeepDOC source checkout.\n"
        "Original Python source files retain Apache-2.0 copyright headers.\n"
        f"Source root: {source_root}\n",
        encoding="utf-8",
    )
    print(f"DeepDOC code prepared at: {code_destination.resolve()}")
    print(f"DeepDOC resources prepared at: {resource_destination.resolve()}")


if __name__ == "__main__":
    main()
