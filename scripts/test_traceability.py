from app.traceability.entity_linker import QualityEntityLinker
from app.traceability.service import ProblemTraceabilityService
from app.traceability.taxonomy import (
    infer_document_type,
    is_traceability_question,
    normalize_document_type,
    normalize_upload_document_type,
)


class _FakeRetriever:
    def retrieve_with_metadata(
        self,
        question,
        top_k=5,
        filters=None,
        multimodal_query=None,
    ):
        return {
            "contexts": [
                {
                    "doc_id": "ll-1",
                    "chunk_id": "ll-1-c1",
                    "source": "LL-MQFH-2024-94 Tharu FDS头部缝隙大.pptx",
                    "doc_type": "LESSON_LEARNED",
                    "text": "FDS 扭矩不足导致钣金变形和头部缝隙大。",
                    "score": 0.92,
                },
                {
                    "doc_id": "standard-1",
                    "chunk_id": "standard-1-c1",
                    "source": "底盘组件及转向系统标准化手册.pdf",
                    "doc_type": "STANDARD",
                    "text": "紧固连接应按规定扭矩执行并进行过程监控。",
                    "score": 0.88,
                },
                {
                    "doc_id": "ll-2",
                    "chunk_id": "ll-2-c1",
                    "source": "another-lesson.pptx",
                    "doc_type": "LESSON_LEARNED",
                    "text": "另一个紧固问题。",
                    "score": 0.7,
                },
            ],
            "metadata": {"retrieval_mode": "hybrid"},
        }


class _FakeGraphService:
    def search_traceability(self, question, *, entities, limit):
        assert entities["process_parameters"][0]["canonical_key"] == "torque"
        return {
            "paths": [
                {
                    "nodes": [
                        {"name": "torque"},
                        {"name": "ll-1-c1"},
                        {"name": "LL-MQFH-2024-94"},
                    ],
                    "relationships": ["MENTIONS", "HAS_CHUNK"],
                }
            ],
            "path_count": 1,
            "context": "证据路径1: torque -[MENTIONS]-> ll-1-c1 -[HAS_CHUNK]-> LL-MQFH-2024-94",
        }


def main() -> None:
    assert infer_document_type("LL-MQFH-2024-94 FDS头部缝隙大.pptx") == "LESSON_LEARNED"
    assert (
        infer_document_type("整车制造过程 标准化管理手册.pdf")
        == "STANDARD_WORK_DOCUMENT"
    )
    assert normalize_document_type("FMEA") == "PFMEA"
    assert normalize_document_type("SOP") == "STANDARD_WORK_DOCUMENT"
    assert normalize_upload_document_type("LESSON_LEARNED") == "LESSON_LEARNED"
    assert (
        normalize_upload_document_type("STANDARD_WORK_DOCUMENT")
        == "STANDARD_WORK_DOCUMENT"
    )
    try:
        normalize_upload_document_type(None)
    except ValueError as exc:
        assert "必须选择" in str(exc)
    else:
        raise AssertionError("missing upload label must be rejected")
    try:
        normalize_upload_document_type("GENERAL")
    except ValueError as exc:
        assert "不支持的文档标签" in str(exc)
    else:
        raise AssertionError("unsupported upload label must be rejected")
    assert is_traceability_question("售后扭矩问题如何追溯到制造标准？")
    assert is_traceability_question("售后出现扭矩问题，制造端有哪些风险？")
    assert is_traceability_question("有没有类似案例和 LessonLearn？")
    assert not is_traceability_question("扭矩标准值是多少？")

    linker = QualityEntityLinker()
    entities = linker.link("Tharu FDS 扭矩不足导致头部缝隙大并可能松动")
    assert entities["vehicle_models"][0]["canonical_key"] == "tharu"
    assert entities["components"][0]["canonical_key"] == "fds_fastener"
    assert entities["process_parameters"][0]["canonical_key"] == "torque"
    assert entities["root_causes"][0]["canonical_key"] == "insufficient_torque"
    assert entities["failure_modes"][0]["canonical_key"] in {
        "loose",
        "gap_excessive",
    }
    assert linker.link("Tiguan L车门问题")["vehicle_models"][0][
        "canonical_key"
    ] == "tiguan_l"
    assert linker.link("Lavida表面压印")["vehicle_models"][0][
        "canonical_key"
    ] == "lavida"
    assert linker.link("Lavida表面压印")["failure_modes"][0][
        "canonical_key"
    ] == "surface_impression"

    service = ProblemTraceabilityService(
        _FakeRetriever(),
        entity_linker=linker,
        graph_service=_FakeGraphService(),
        graph_enabled=True,
    )
    result = service.trace(
        "Tharu FDS 扭矩不足导致头部缝隙大，有哪些制造标准和 LessonLearn 风险？",
        top_k=2,
    )
    assert result["metadata"]["traceability_enabled"] is True
    assert result["metadata"]["knowledge_graph_path_count"] == 1
    assert result["metadata"]["traceability_case_count"] == 1
    assert [case["case_id"] for case in result["cases"]] == ["ll-1"]
    assert result["metadata"]["traceability_document_type_counts"] == {
        "LESSON_LEARNED": 1,
        "STANDARD_WORK_DOCUMENT": 1,
    }
    assert result["contexts"][0]["traceability_role"] == "lesson_learned"
    assert any(
        context["doc_type"] == "KNOWLEDGE_GRAPH"
        for context in result["contexts"]
    )
    case_search = service.enrich_retrieval(
        "Tharu FDS扭矩有哪些历史案例？",
        _FakeRetriever().retrieve_with_metadata("case search"),
        top_k=2,
        task_mode="case_search",
    )
    assert [item["doc_id"] for item in case_search["contexts"][:2]] == [
        "ll-1",
        "ll-2",
    ]
    assert [case["case_id"] for case in case_search["cases"]] == [
        "ll-1",
        "ll-2",
    ]

    bundle_service = ProblemTraceabilityService(
        _FakeRetriever(),
        entity_linker=linker,
    )
    bundled_case = bundle_service.enrich_retrieval(
        "有没有无锡万华的缺陷案例？",
        {
            "contexts": [
                {
                    "doc_id": "wuxi-wanhua",
                    "chunk_id": "wuxi-wanhua-c1",
                    "chunk_index": 1,
                    "page_number": 1,
                    "table_index": 1,
                    "source": "无锡万华缺陷案例.pptx",
                    "doc_type": "LESSON_LEARNED",
                    "text": "供应商：无锡万华。分析结果 / 措施",
                    "score": 0.95,
                },
                {
                    "doc_id": "wuxi-wanhua",
                    "chunk_id": "wuxi-wanhua-c2",
                    "chunk_index": 2,
                    "page_number": 1,
                    "table_index": 1,
                    "source": "无锡万华缺陷案例.pptx",
                    "doc_type": "LESSON_LEARNED",
                    "text": "制造原因：模具冲头磨损。措施：更换冲头和凹模套。",
                    "score": 0.94,
                    "retrieval_source": "adjacent",
                    "adjacent_to_chunk_id": "wuxi-wanhua-c1",
                },
                {
                    "doc_id": "other-case",
                    "chunk_id": "other-case-c1",
                    "chunk_index": 0,
                    "page_number": 1,
                    "source": "其他供应商案例.pptx",
                    "doc_type": "LESSON_LEARNED",
                    "text": "其他供应商案例。",
                    "score": 0.80,
                },
            ],
            "metadata": {"retrieval_mode": "hybrid"},
        },
        top_k=2,
        task_mode="case_search",
    )
    assert len(bundled_case["contexts"]) == 2
    assert bundled_case["contexts"][0]["evidence_chunk_ids"] == [
        "wuxi-wanhua-c1",
        "wuxi-wanhua-c2",
    ]
    assert bundled_case["contexts"][0]["evidence_chunk_count"] == 2
    assert "更换冲头和凹模套" in bundled_case["contexts"][0]["text"]
    assert bundled_case["metadata"]["traceability_evidence_bundle_count"] == 1
    assert bundled_case["metadata"]["traceability_bundled_chunk_count"] == 3
    assert bundled_case["cases"][0]["evidence_chunk_count"] == 2
    assert bundled_case["cases"][0]["chunk_ids"] == [
        "wuxi-wanhua-c1",
        "wuxi-wanhua-c2",
    ]
    print("Unified quality traceability tests passed with fake backends")


if __name__ == "__main__":
    main()
