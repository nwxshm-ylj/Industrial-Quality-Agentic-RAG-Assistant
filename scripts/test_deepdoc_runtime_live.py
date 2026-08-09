from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import requests


def _build_test_pdf(path: Path) -> None:
    stream = (
        b"BT /F1 18 Tf 72 720 Td "
        b"(Industrial quality inspection guide) Tj ET"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> "
            b"/Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(payload)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a real PDF parse against the DeepDOC HTTP runtime."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:18010",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="deepdoc-live-") as directory:
        pdf_path = Path(directory) / "deepdoc_live_test.pdf"
        _build_test_pdf(pdf_path)
        with pdf_path.open("rb") as file_handle:
            response = requests.post(
                f"{args.base_url.rstrip('/')}/v1/parse",
                files={"file": (pdf_path.name, file_handle, "application/pdf")},
                data={"zoomin": "2", "max_pages": "10"},
                timeout=(5, 300),
            )
        response.raise_for_status()
        payload = response.json()

    assert payload["metadata"]["runtime"] == "infiniflow-deepdoc"
    assert isinstance(payload.get("sections"), list)
    assert isinstance(payload.get("tables"), list)
    print(
        "DeepDOC live parse passed:",
        {
            "runtime": payload["metadata"]["runtime"],
            "sections": len(payload["sections"]),
            "tables": len(payload["tables"]),
        },
    )


if __name__ == "__main__":
    main()
