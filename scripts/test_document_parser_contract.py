from pathlib import Path
from tempfile import TemporaryDirectory

from app.rag.loader import SUPPORTED_DOCUMENT_EXTENSIONS, load_single_document
from app.rag.parsing.contracts import ParsedDocument
from app.rag.parsing.exceptions import UnsupportedDocumentFormatError
from app.rag.parsing.router import get_document_parser_router


def main() -> None:
    router = get_document_parser_router()
    assert router is get_document_parser_router(), "parser router must be process-scoped"
    assert SUPPORTED_DOCUMENT_EXTENSIONS == {
        ".md",
        ".txt",
        ".pdf",
        ".docx",
        ".pptx",
    }

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        document_path = root / "quality_rule.md"
        document_path.write_text(
            "# 轮毂识别异常\n\n优先检查相机连接和成像质量。\n",
            encoding="utf-8",
        )

        result = load_single_document(str(document_path))
        assert result["parser"] == "structured-v1"
        assert result["parser_name"] == "structured-v1"
        assert result["parser_version"] == "structured-v1"
        assert result["sections"] == result["elements"]
        assert result["elements"][0]["element_id"].startswith("element_")
        assert result["elements"][0]["element_type"] == "heading"
        assert result["elements"][0]["section_type"] == "heading"

        normalized = ParsedDocument.from_mapping(result)
        assert normalized.source == document_path.name
        assert normalized.elements[0].heading_path == ("轮毂识别异常",)
        assert normalized.to_dict()["sections"] == result["sections"]

        unsupported_path = root / "unsupported.csv"
        unsupported_path.write_text("value", encoding="utf-8")
        try:
            load_single_document(str(unsupported_path))
        except UnsupportedDocumentFormatError as exc:
            assert ".csv" in str(exc)
        else:
            raise AssertionError("unsupported document format must fail")

    print("Document parser contract tests passed")


if __name__ == "__main__":
    main()
