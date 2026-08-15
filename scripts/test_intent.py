from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import app.graph.nodes.intent_router_node as router_module
from app.graph.query_features import normalize_intent_label


@dataclass
class FakeResponse:
    content: str
    usage_metadata: dict[str, int] = field(
        default_factory=lambda: {
            "input_tokens": 5,
            "output_tokens": 1,
            "total_tokens": 6,
        }
    )
    response_metadata: dict[str, Any] = field(default_factory=dict)


class FakeChatModel:
    def __init__(self, content: str) -> None:
        self.content = content

    def invoke(self, messages: list[Any]) -> FakeResponse:
        return FakeResponse(self.content)


def _route(question: str, model_output: str) -> dict:
    original = router_module.llm
    router_module.llm = FakeChatModel(model_output)
    try:
        return router_module.intent_router_node(
            {
                "question": question,
                "request_id": "intent-test",
                "session_id": "intent-test",
                "memory_messages": [],
                "intent": "rag",
                "retry_count": 0,
            }
        )
    finally:
        router_module.llm = original


def main() -> None:
    assert normalize_intent_label("fault_diagnosis") == "rag"
    assert normalize_intent_label("case_search") == "rag"
    assert normalize_intent_label("sql_analysis") == "sql"

    standard = _route("标准手册规定的最高允许扭矩是多少？", "sql")
    assert standard["intent"] == "rag"

    statistics = _route("最近一周工位报警记录有多少条？", "rag")
    assert statistics["intent"] == "sql"
    assert statistics["query_features"]["structured_data_required"] is True

    diagnosis = _route("轮毂识别异常的原因和排查步骤是什么？", "rag")
    assert diagnosis["intent"] == "rag"
    assert diagnosis["query_features"]["diagnosis_required"] is True
    assert "root_cause" in diagnosis["query_features"]["requested_aspects"]

    traceability = _route("有没有类似LessonLearn和售后风险？", "rag")
    assert traceability["intent"] == "rag"
    assert traceability["query_features"]["traceability_required"] is True
    assert set(traceability["query_features"]["preferred_doc_types"]) == {
        "LESSON_LEARNED",
        "STANDARD_WORK_DOCUMENT",
        "PFMEA",
        "AFTERSALES_DOCUMENT",
    }

    historical_case = _route("查询历史案例中的处理措施", "rag")
    assert historical_case["query_features"]["traceability_required"] is True

    greeting = _route("你好", "rag")
    assert greeting["intent"] == "general"
    print("Three-intent router and query features test passed")


if __name__ == "__main__":
    main()
