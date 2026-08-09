from pathlib import Path
from tempfile import TemporaryDirectory

from app.rag.parsing.deepdoc_http_runtime import (
    DeepDocHttpRuntime,
    get_deepdoc_http_runtime,
)
from app.rag.parsing.exceptions import (
    DocumentParsingError,
    ParserUnavailableError,
)


class _Response:
    def __init__(self, status_code: int, payload, text: str = "") -> None:
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        return self.payload


class _Client:
    def __init__(self) -> None:
        self.post_response = _Response(
            200,
            {
                "sections": [["wheel text", "@@1\t1\t2\t3\t4##"]],
                "tables": [],
                "metadata": {"runtime": "mock-http"},
            },
        )
        self.get_response = _Response(
            200,
            {"status": "ready", "engine": "mock-http"},
        )
        self.post_calls = []
        self.get_calls = []

    def post(self, url, *, files, data, timeout):
        assert files["file"][1].read(4) == b"%PDF"
        self.post_calls.append((url, data, timeout))
        return self.post_response

    def get(self, url, *, timeout):
        self.get_calls.append((url, timeout))
        return self.get_response


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / "manual.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        client = _Client()
        runtime = DeepDocHttpRuntime(
            "http://deepdoc-runtime:8010",
            connect_timeout_seconds=3,
            read_timeout_seconds=120,
            client=client,
        )
        payload = runtime.parse_pdf(pdf_path, zoomin=3, max_pages=50)
        assert payload["metadata"]["runtime"] == "mock-http"
        assert client.post_calls == [
            (
                "http://deepdoc-runtime:8010/v1/parse",
                {"zoomin": "3", "max_pages": "50"},
                (3, 120),
            )
        ]
        ready = runtime.readiness(timeout_seconds=2)
        assert ready["status"] == "ready"
        assert client.get_calls == [
            ("http://deepdoc-runtime:8010/health/ready", (2, 2))
        ]

        client.post_response = _Response(503, {"detail": "models missing"})
        try:
            runtime.parse_pdf(pdf_path, zoomin=3, max_pages=50)
        except ParserUnavailableError as exc:
            assert "models missing" in str(exc)
        else:
            raise AssertionError("HTTP 503 must be treated as unavailable")

        client.post_response = _Response(415, {"detail": "invalid PDF"})
        try:
            runtime.parse_pdf(pdf_path, zoomin=3, max_pages=50)
        except DocumentParsingError as exc:
            assert "invalid PDF" in str(exc)
        else:
            raise AssertionError("HTTP 4xx must be treated as a parsing error")

    first = get_deepdoc_http_runtime("http://runtime:8010", 5, 300)
    second = get_deepdoc_http_runtime("http://runtime:8010", 5, 300)
    assert first is second, "HTTP connection pool must be process-reused"
    print("DeepDOC HTTP runtime client tests passed without network")


if __name__ == "__main__":
    main()
