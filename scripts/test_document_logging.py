from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from app.services.document_service import DocumentService


def main() -> None:
    with TemporaryDirectory() as directory:
        service = DocumentService(uploads_dir=directory)
        with (
            patch("app.services.document_service.record_document_operation"),
            patch("app.services.document_service.logger.log") as log_mock,
        ):
            service._log_event(
                "document_parsed",
                perf_counter(),
                doc_id="doc-1",
                filename="lesson-learn.pptx",
                doc_type="LessonLearn",
                version="v1",
                status="uploaded",
                parser_name="structured-v1",
                parser_version="structured-v1",
                multimodal_asset_count=3,
                ocr_element_count=2,
            )

    event_data = log_mock.call_args.kwargs["extra"]["event_data"]
    assert event_data["parser_name"] == "structured-v1"
    assert event_data["parser_version"] == "structured-v1"
    assert event_data["multimodal_asset_count"] == 3
    assert event_data["ocr_element_count"] == 2
    assert event_data["doc_id"] == "doc-1"
    assert event_data["status"] == "uploaded"
    print("Document structured logging test passed")


if __name__ == "__main__":
    main()
