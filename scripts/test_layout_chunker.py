from app.rag.chunking.layout_chunker import (
    LayoutChunker,
    LayoutChunkerConfig,
    scope_chunk_id,
)
from app.rag.chunking.token_counter import UnicodeTokenCounter
from app.rag.splitter import split_docs


def _document() -> dict:
    table_rows = "\n".join(
        f"| HUB-{index:03d} | 检查相机连接、曝光和识别阈值 |"
        for index in range(1, 15)
    )
    return {
        "source": "wheel_quality_manual.pdf",
        "content": "轮毂识别异常处理规范",
        "file_ext": ".pdf",
        "parser": "deepdoc",
        "parser_name": "deepdoc",
        "parser_version": "deepdoc-layout-v1",
        "metadata": {"doc_type": "quality_standard"},
        "elements": [
            {
                "element_id": "heading-1",
                "element_type": "heading",
                "section_type": "heading",
                "text": "轮毂识别异常",
                "heading_path": ["故障诊断", "轮毂识别异常"],
                "heading_level": 2,
                "page_number": 3,
            },
            {
                "element_id": "paragraph-1",
                "element_type": "paragraph",
                "section_type": "paragraph",
                "text": "优先检查相机连接、成像曝光和触发信号。" * 10,
                "heading_path": ["故障诊断", "轮毂识别异常"],
                "page_number": 3,
                "bbox": [10, 20, 300, 180],
                "reading_order": 1,
            },
            {
                "element_id": "paragraph-2",
                "element_type": "paragraph",
                "section_type": "paragraph",
                "text": "确认图像质量后，再检查识别规则和模型阈值。" * 5,
                "heading_path": ["故障诊断", "轮毂识别异常"],
                "page_number": 4,
                "bbox": [10, 20, 300, 160],
                "reading_order": 2,
            },
            {
                "element_id": "table-1",
                "element_type": "table",
                "section_type": "table",
                "text": (
                    "| 故障代码 | 优先排查项 |\n"
                    "| --- | --- |\n"
                    f"{table_rows}"
                ),
                "heading_path": ["故障诊断", "轮毂识别异常"],
                "page_number": 5,
                "table_index": 1,
                "bbox": [12, 80, 520, 700],
            },
        ],
    }


def main() -> None:
    counter = UnicodeTokenCounter()
    config = LayoutChunkerConfig(
        target_tokens=48,
        max_tokens=64,
        overlap_tokens=8,
    )
    chunker = LayoutChunker(config, token_counter=counter)
    first = chunker.split_document(_document())
    second = chunker.split_document(_document())

    assert first
    assert [item["metadata"]["chunk_id"] for item in first] == [
        item["metadata"]["chunk_id"] for item in second
    ]
    assert len({item["metadata"]["chunk_id"] for item in first}) == len(first)
    assert all(item["metadata"]["chunk_strategy"] == "layout-token-v2" for item in first)
    assert all(item["metadata"]["parser_version"] == "deepdoc-layout-v1" for item in first)
    assert all(item["metadata"]["token_counter"] == "unicode-estimator-v1" for item in first)
    assert all(item["metadata"]["token_count"] <= config.max_tokens for item in first)
    assert all(
        item["metadata"]["token_count"] == counter.count(item["text"])
        for item in first
    )
    assert any(item["metadata"]["page_start"] == 3 for item in first)
    assert any(item["metadata"]["page_end"] == 4 for item in first)
    assert any(item["metadata"]["bboxes"] for item in first)
    assert any("paragraph-1" in item["metadata"]["element_ids"] for item in first)

    table_chunks = [
        item for item in first if item["metadata"]["section_type"] == "table"
    ]
    assert len(table_chunks) > 1
    assert all("| 故障代码 | 优先排查项 |" in item["text"] for item in table_chunks)
    assert all(item["metadata"]["table_index"] == 1 for item in table_chunks)

    facade_chunks = split_docs(
        [_document()],
        chunk_strategy="layout_token_v2",
        target_tokens=48,
        max_tokens=64,
        overlap_tokens=8,
        token_counter=counter,
    )
    assert [item["metadata"]["chunk_id"] for item in facade_chunks] == [
        item["metadata"]["chunk_id"] for item in first
    ]

    assert scope_chunk_id(
        "doc-test",
        first[0]["metadata"]["chunk_id"],
        operation_id="operation-1",
    ).startswith("doc-test_operation-1_chunk_")
    print("Layout-aware chunker tests passed")


if __name__ == "__main__":
    main()
