from app.rag.chunking.layout_chunker import LayoutChunker, LayoutChunkerConfig
from app.rag.parsing.merge import merge_structured_and_multimodal


def _asset(asset_id: str, page_number: int, text: str) -> dict:
    return {
        "text": text,
        "metadata": {
            "asset_id": asset_id,
            "page_number": page_number,
            "modality": "text+image",
            "mime_type": "image/png",
        },
    }


def main() -> None:
    structured = {
        "source": "wheel_manual.pdf",
        "content": "轮毂识别异常\n检查相机连接\n第二页原生文字",
        "file_ext": ".pdf",
        "parser": "deepdoc",
        "parser_name": "deepdoc",
        "parser_version": "deepdoc-layout-v1",
        "elements": [
            {
                "text": "轮毂识别异常",
                "element_type": "title",
                "heading_path": ["轮毂识别异常"],
                "heading_level": 1,
                "page_number": 1,
                "reading_order": 1,
            },
            {
                "text": "检查相机连接",
                "element_type": "paragraph",
                "heading_path": ["轮毂识别异常"],
                "page_number": 1,
                "reading_order": 2,
            },
            {
                "text": "第二页原生文字",
                "element_type": "paragraph",
                "page_number": 2,
                "reading_order": 1,
            },
            {
                "text": "标签 A",
                "element_type": "paragraph",
                "page_number": 4,
                "reading_order": 1,
            },
        ],
        "metadata": {"runtime": "mock-deepdoc"},
    }
    multimodal = {
        "source": "wheel_manual.pdf",
        "content": "multimodal text",
        "file_ext": ".pdf",
        "parser": "multimodal-v1",
        "assets": [
            _asset(
                "asset-page-1",
                1,
                "检查相机连接\n\n[OCR]\n确认镜头曝光参数",
            ),
            _asset("asset-page-2", 2, "第二页原生文字"),
            _asset("asset-page-3", 3, "仅扫描页 OCR 文本"),
            _asset("asset-page-4", 4, "标签 A\n标签 B"),
        ],
        "asset_dir": "data/assets/test",
    }

    merged = merge_structured_and_multimodal(structured, multimodal)
    assert merged["parser"] == "deepdoc+multimodal-v1"
    assert merged["parser_version"] == "deepdoc-layout-v1+multimodal-v1"
    assert merged["metadata"]["multimodal_merged"] is True
    assert merged["metadata"]["multimodal_asset_count"] == 4
    assert merged["metadata"]["ocr_element_count"] == 3

    elements = merged["elements"]
    page_one = [item for item in elements if item["page_number"] == 1]
    assert all("asset-page-1" in item["asset_ids"] for item in page_one)
    assert any(
        item["element_type"] == "ocr_text"
        and item["text"] == "确认镜头曝光参数"
        for item in page_one
    )
    page_two = [item for item in elements if item["page_number"] == 2]
    assert len(page_two) == 1, "native text must not be duplicated"
    assert page_two[0]["asset_id"] == "asset-page-2"
    page_three = [item for item in elements if item["page_number"] == 3]
    assert len(page_three) == 1
    assert page_three[0]["element_type"] == "ocr_text"
    assert page_three[0]["asset_id"] == "asset-page-3"
    page_four = [item for item in elements if item["page_number"] == 4]
    assert len(page_four) == 2
    assert any(item["text"] == "标签 B" for item in page_four)

    chunks = LayoutChunker(
        LayoutChunkerConfig(
            target_tokens=64,
            max_tokens=96,
            overlap_tokens=8,
        )
    ).split_document(merged)
    assert chunks
    assert any("确认镜头曝光参数" in chunk["text"] for chunk in chunks)
    assert any(
        "asset-page-1" in chunk["metadata"]["asset_ids"]
        for chunk in chunks
    )
    assert any(
        "asset-page-3" in chunk["metadata"]["asset_ids"]
        for chunk in chunks
    )

    multimodal_only = merge_structured_and_multimodal(None, multimodal)
    assert multimodal_only["parser"] == "multimodal-v1"

    print("Structured + multimodal parser merge tests passed")


if __name__ == "__main__":
    main()
