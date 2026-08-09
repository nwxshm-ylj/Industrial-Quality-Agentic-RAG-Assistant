from io import BytesIO
from pathlib import Path

from starlette.datastructures import UploadFile

from deepdoc_runtime import main as runtime_main


class _FakeEngine:
    def __init__(self) -> None:
        self.calls = []

    def parse_pdf(self, path: Path, *, zoomin: int, max_pages: int):
        assert path.read_bytes().startswith(b"%PDF")
        self.calls.append((zoomin, max_pages))
        return {
            "sections": [["runtime text", "@@1\t1\t2\t3\t4##"]],
            "tables": [],
            "metadata": {"runtime": "fake"},
        }


def main() -> None:
    fake_engine = _FakeEngine()
    original_get_engine = runtime_main.get_engine
    runtime_main.get_engine = lambda: fake_engine
    try:
        ready = runtime_main.readiness()
        assert ready["status"] == "ready"
        upload = UploadFile(
            filename="manual.pdf",
            file=BytesIO(b"%PDF-1.4 mock runtime input"),
        )
        result = runtime_main.parse_pdf(upload, zoomin=3, max_pages=25)
        assert result["metadata"]["runtime"] == "fake"
        assert fake_engine.calls == [(3, 25)]
        assert upload.file.closed
    finally:
        runtime_main.get_engine = original_get_engine
    print("DeepDOC runtime API tests passed with fake engine")


if __name__ == "__main__":
    main()
