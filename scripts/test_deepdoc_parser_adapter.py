import sys
from types import ModuleType
from pathlib import Path
from tempfile import TemporaryDirectory

from app.rag.loader import load_single_document
from app.rag.parsing.contracts import DocumentElement, ParsedDocument
from app.rag.parsing.deepdoc_adapter import (
    DeepDocParserAdapter,
    normalize_deepdoc_result,
)
from app.rag.parsing.exceptions import DocumentParsingError, ParserUnavailableError
from app.rag.parsing.router import DocumentParserRouter


class _FakeRuntime:
    def __init__(self) -> None:
        self.calls = []

    def parse_pdf(self, path: Path, *, zoomin: int, max_pages: int):
        self.calls.append((path, zoomin, max_pages))
        return {
            "sections": [
                {
                    "text": "轮毂识别异常",
                    "layout_type": "title",
                    "heading_level": 1,
                    "page_number": 1,
                    "bbox": [10, 20, 300, 55],
                    "reading_order": 1,
                },
                {
                    "text": "优先检查相机连接和成像曝光。",
                    "layout_type": "text",
                    "page_number": 1,
                    "x0": 10,
                    "top": 70,
                    "x1": 500,
                    "bottom": 120,
                    "reading_order": 2,
                },
            ],
            "tables": [
                (
                    (
                        None,
                        "<table><tr><th>故障代码</th><th>措施</th></tr>"
                        "<tr><td>HUB-101</td><td>检查相机</td></tr></table>",
                    ),
                    "@@2\t12\t520\t80\t680##",
                ),
                ((object(), ["图 1 相机安装位置"]), "@@3\t20\t420\t60\t360##"),
            ],
            "metadata": {"runtime": "mock-deepdoc"},
        }


class _FailingParser:
    name = "deepdoc"
    version = "deepdoc-layout-v1"
    supported_extensions = frozenset({".pdf"})

    def parse(self, path: Path) -> ParsedDocument:
        raise DocumentParsingError(f"mock parse failure: {path.name}")


class _FallbackParser:
    name = "structured-v1"
    version = "structured-v1"
    supported_extensions = frozenset({".pdf"})

    def parse(self, path: Path) -> ParsedDocument:
        element = DocumentElement.from_mapping(
            {"text": "native fallback", "section_type": "paragraph"},
            source=path.name,
            index=0,
        )
        return ParsedDocument(
            source=path.name,
            content=element.text,
            file_ext=".pdf",
            elements=(element,),
            parser_name=self.name,
            parser_version=self.version,
        )


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        pdf_path = root / "quality_manual.pdf"
        # The adapter test uses a mock runtime, so a PDF signature is enough and
        # keeps the default unit-test path independent from PyMuPDF/model assets.
        pdf_path.write_bytes(b"%PDF-1.4\n% mock DeepDOC input\n")

        runtime = _FakeRuntime()
        load_count = 0

        def load_runtime():
            nonlocal load_count
            load_count += 1
            return runtime

        adapter = DeepDocParserAdapter(
            load_runtime,
            require_model_files=False,
            zoomin=3,
            max_pages=100,
        )
        first = adapter.parse(pdf_path)
        second = adapter.parse(pdf_path)
        assert load_count == 1, "DeepDOC runtime must be process-reused"
        assert len(runtime.calls) == 2
        assert first.parser_name == "deepdoc"
        assert first.parser_version == "deepdoc-layout-v1"
        assert first.metadata["runtime"] == "mock-deepdoc"
        assert first.metadata["element_counts"] == {
            "title": 1,
            "paragraph": 1,
            "table": 1,
            "figure_caption": 1,
        }
        assert first.elements[0].bbox == (10.0, 20.0, 300.0, 55.0)
        assert first.elements[1].heading_path == ("轮毂识别异常",)
        table = next(element for element in first.elements if element.element_type == "table")
        assert table.page_number == 2
        assert "| 故障代码 | 措施 |" in table.text
        assert "| HUB-101 | 检查相机 |" in table.text
        figure = next(
            element
            for element in first.elements
            if element.element_type == "figure_caption"
        )
        assert figure.text == "图 1 相机安装位置"
        assert figure.page_number == 3
        assert figure.metadata["has_image"] is True
        assert second.content == first.content

        runtime_module = ModuleType("mock_deepdoc_runtime")
        runtime_module.build = lambda: runtime
        sys.modules[runtime_module.__name__] = runtime_module
        try:
            routed = load_single_document(
                str(pdf_path),
                parser_backend="auto",
                parser_fallback="native",
                deepdoc_enabled=True,
                deepdoc_runtime_factory="mock_deepdoc_runtime:build",
                deepdoc_require_model_files=False,
                deepdoc_zoomin=3,
                deepdoc_max_pages=100,
            )
            assert routed["parser"] == "deepdoc"
            assert routed["parser_version"] == "deepdoc-layout-v1"
        finally:
            sys.modules.pop(runtime_module.__name__, None)

        tuple_elements, _ = normalize_deepdoc_result(
            (
                [("定位文本@@3\t11\t210\t31\t61##", "@@3\t11\t210\t31\t61##")],
                [((None, [["代码", "措施"], ["A-1", "复位"]]), "@@4\t1\t9\t2\t8##")],
            ),
            source="tuple.pdf",
        )
        assert tuple_elements[0].text == "定位文本"
        assert tuple_elements[0].page_number == 3
        assert tuple_elements[0].bbox == (11.0, 31.0, 210.0, 61.0)
        assert tuple_elements[1].element_type == "table"
        assert "| 代码 | 措施 |" in tuple_elements[1].text

        router = DocumentParserRouter()
        router.register(_FallbackParser(), make_default=True)
        router.register(_FailingParser())
        fallback = router.parse(
            pdf_path,
            parser_name="deepdoc",
            fallback_parser_name="structured-v1",
        )
        assert fallback.parser_name == "structured-v1"
        assert fallback.metadata["parser_fallback_from"] == "deepdoc"
        assert "mock parse failure" in fallback.metadata["parser_fallback_reason"]

        missing_models = DeepDocParserAdapter(
            load_runtime,
            model_dir=root / "missing-models",
            require_model_files=True,
        )
        try:
            missing_models.parse(pdf_path)
        except ParserUnavailableError as exc:
            assert "模型目录不存在" in str(exc)
        else:
            raise AssertionError("missing DeepDOC models must fail before runtime load")

        incomplete_models = root / "incomplete-models"
        incomplete_models.mkdir()
        for filename in (
            "det.onnx",
            "rec.onnx",
            "layout.onnx",
            "tsr.onnx",
            "updown_concat_xgb.model",
        ):
            (incomplete_models / filename).write_bytes(b"mock")
        missing_ocr_dictionary = DeepDocParserAdapter(
            load_runtime,
            model_dir=incomplete_models,
            require_model_files=True,
        )
        try:
            missing_ocr_dictionary.parse(pdf_path)
        except ParserUnavailableError as exc:
            assert "ocr.res" in str(exc)
        else:
            raise AssertionError("DeepDOC OCR dictionary must be validated")

    print("DeepDOC parser adapter tests passed without model loading")


if __name__ == "__main__":
    main()
