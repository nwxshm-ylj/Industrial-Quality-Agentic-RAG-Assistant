from __future__ import annotations

import app.graph.nodes.intent_router_node as router_module
from app.graph.query_features import normalize_intent_label


def _route(question: str, memory_messages: list[dict] | None = None) -> dict:
    return router_module.intent_router_node(
        {
            "question": question,
            "request_id": "intent-test",
            "session_id": "intent-test",
            "memory_messages": memory_messages or [],
            "intent": "rag",
            "retry_count": 0,
        }
    )


def main() -> None:
    assert normalize_intent_label("fault_diagnosis") == "rag"
    assert normalize_intent_label("case_search") == "rag"
    assert normalize_intent_label("sql_analysis") == "sql"

    standard = _route("标准手册规定的最高允许扭矩是多少？")
    assert standard["intent"] == "rag"

    statistics = _route("最近一周工位报警记录有多少条？")
    assert statistics["intent"] == "sql"
    assert statistics["query_features"]["structured_data_required"] is True

    diagnosis = _route("轮毂识别异常的原因和排查步骤是什么？")
    assert diagnosis["intent"] == "rag"
    assert diagnosis["query_features"]["diagnosis_required"] is True
    assert "root_cause" in diagnosis["query_features"]["requested_aspects"]

    traceability = _route("有没有类似LessonLearn和售后风险？")
    assert traceability["intent"] == "rag"
    assert traceability["query_features"]["traceability_required"] is True
    assert set(traceability["query_features"]["preferred_doc_types"]) == {
        "LESSON_LEARNED",
        "STANDARD_WORK_DOCUMENT",
        "PFMEA",
        "AFTERSALES_DOCUMENT",
    }

    historical_case = _route("查询历史案例中的处理措施")
    assert historical_case["query_features"]["traceability_required"] is True

    greeting = _route("你好")
    assert greeting["intent"] == "general"

    ambiguous_follow_up = _route(
        "那二月份呢？",
        memory_messages=[
            {"role": "user", "content": "最近一周工位报警记录有多少条？"}
        ],
    )
    assert ambiguous_follow_up["intent"] == "rag"

    assert router_module.route_after_intent({"intent": "sql_analysis"}) == "sql"
    assert router_module.route_after_intent({"intent": "case_search"}) == "rag"
    assert router_module.route_after_intent({"intent": "unknown"}) == "rag"
    print("Deterministic three-intent router and query features test passed")


if __name__ == "__main__":
    main()
