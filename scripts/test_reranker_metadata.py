from __future__ import annotations

from app.rag.reranker import IndustrialReranker


class _FakeCrossEncoder:
    def __init__(self) -> None:
        self.pairs: list[list[str]] = []

    def predict(self, pairs: list[list[str]]) -> list[float]:
        self.pairs = pairs
        return [0.25, 0.9]


def main() -> None:
    model = _FakeCrossEncoder()
    reranker = IndustrialReranker(model=model)
    documents = [
        {
            "chunk_id": "chunk-a",
            "source": "表面匹配手册.pdf",
            "doc_type": "标准作业文档",
            "heading_path": ["项目阶段", "输入"],
            "page_start": 13,
            "page_end": 14,
            "text": "表面匹配输入内容",
        },
        {
            "chunk_id": "chunk-b",
            "source": "车身尺寸模块.pdf",
            "doc_type": "标准作业文档",
            "page_number": 15,
            "text": "KT、白车身匹配和FMK输入及评价方法",
        },
    ]

    result = reranker.rerank("车身尺寸管理的核心输入", documents, top_k=2)

    assert result[0]["chunk_id"] == "chunk-b"
    assert result[0]["rerank_score"] == 0.9
    assert "[文档] 表面匹配手册.pdf" in model.pairs[0][1]
    assert "[文档类型] 标准作业文档" in model.pairs[0][1]
    assert "[章节] 项目阶段 > 输入" in model.pairs[0][1]
    assert "[页码] 13-14" in model.pairs[0][1]
    assert "[正文]\n表面匹配输入内容" in model.pairs[0][1]
    assert "[页码] 15" in model.pairs[1][1]
    print("Reranker metadata formatting tests passed")


if __name__ == "__main__":
    main()
