from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Any

from app.core.telemetry_context import (
    get_request_context,
    reset_request_context,
    start_request_context,
)
from app.rag.generator import AnswerGenerator
from app.tools.sql_tool import IndustrialSQLTool


@dataclass
class FakeResponse:
    content: str
    usage_metadata: dict[str, int] = field(
        default_factory=lambda: {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }
    )
    response_metadata: dict[str, Any] = field(default_factory=dict)


class FakeChatModel:
    def __init__(self, content: str) -> None:
        self.content = content

    def invoke(self, messages: list[Any]) -> FakeResponse:
        assert len(messages) == 2
        return FakeResponse(content=self.content)


def main() -> None:
    intent_module = importlib.import_module(
        "app.graph.nodes.intent_router_node"
    )
    rewriter_module = importlib.import_module(
        "app.graph.nodes.query_rewriter_node"
    )
    intent_module.llm = FakeChatModel("fault_diagnosis")
    rewriter_module.llm = FakeChatModel("轮毂 视觉识别 异常 摄像头 OCR 排查")

    token = start_request_context("prompt-components-mock")
    try:
        intent_result = intent_module.intent_router_node(
            {
                "question": "轮毂识别异常可能是什么原因？",
                "request_id": "prompt-components-mock",
                "session_id": "prompt-components-session",
                "memory_messages": [],
                "intent": "doc_qa",
                "retry_count": 0,
            }
        )
        assert intent_result["intent"] == "fault_diagnosis"

        rewrite_result = rewriter_module.query_rewriter_node(
            {
                "question": "那优先排查哪个？",
                "request_id": "prompt-components-mock",
                "session_id": "prompt-components-session",
                "memory_messages": [
                    {
                        "role": "user",
                        "content": "轮毂识别异常可能是什么原因？",
                    }
                ],
                "intent": "fault_diagnosis",
                "retry_count": 0,
            }
        )
        assert "轮毂" in rewrite_result["rewritten_query"]

        generator = AnswerGenerator()
        generator.llm = FakeChatModel("优先检查摄像头污染和安装位置。")
        answer = generator.generate(
            question="那优先排查哪个？",
            contexts=[
                {
                    "source": "wheel.md",
                    "doc_type": "SOP",
                    "chunk_id": "wheel-1",
                    "text": "识别异常时优先检查摄像头污染和安装位置。",
                }
            ],
            memory_messages=[],
        )
        assert "摄像头" in answer

        sql_tool = IndustrialSQLTool()
        sql_tool.llm = FakeChatModel(
            "SELECT station, COUNT(*) AS alarm_count "
            "FROM equipment_alarm GROUP BY station LIMIT 10;"
        )
        sql = sql_tool.generate_sql("哪个工位报警最多？")
        assert sql.lower().startswith("select")
        sql_tool.validate_and_fix_sql(sql)

        context = get_request_context()
        assert context is not None
        assert len(context.ai_events) == 4
        prompt_ids = {
            event.metadata.get("prompt_id")
            for event in context.ai_events
        }
        assert prompt_ids == {
            "industrial.intent_router",
            "industrial.query_rewriter.initial",
            "industrial.answer_generator",
            "industrial.sql_generator",
        }
        for event in context.ai_events:
            assert event.metadata.get("prompt_version") == "1.0.0"
            assert event.metadata.get("prompt_release")

        print("Prompt component mock test passed")
    finally:
        reset_request_context(token)


if __name__ == "__main__":
    main()
