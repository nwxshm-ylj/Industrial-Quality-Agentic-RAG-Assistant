from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.telemetry_context import (
    get_request_context,
    reset_request_context,
    start_request_context,
)
from app.observability.model_usage import (
    extract_chat_usage,
    invoke_observed_chat_model,
)


@dataclass
class FakeResponse:
    content: str = "mock answer"
    usage_metadata: dict[str, Any] = field(
        default_factory=lambda: {
            "input_tokens": 12,
            "output_tokens": 7,
            "total_tokens": 19,
        }
    )
    response_metadata: dict[str, Any] = field(default_factory=dict)


class FakeChatModel:
    def invoke(self, messages: list[Any]) -> FakeResponse:
        assert messages
        return FakeResponse()


def main() -> None:
    usage = extract_chat_usage(FakeResponse())
    assert usage["input_tokens"] == 12
    assert usage["output_tokens"] == 7
    assert usage["total_tokens"] == 19
    assert usage["measurement_source"] == "provider"

    token = start_request_context("mock-model-request")
    try:
        response = invoke_observed_chat_model(
            FakeChatModel(),
            ["hello"],
            component="mock_component",
            provider="mock",
            model_name="mock-chat",
        )
        assert response.content == "mock answer"
        context = get_request_context()
        assert context is not None
        assert len(context.ai_events) == 1
        event = context.ai_events[0]
        assert event.input_tokens == 12
        assert event.output_tokens == 7
        assert event.measurement_source == "provider"
        print("Observed model usage mock test passed")
    finally:
        reset_request_context(token)


if __name__ == "__main__":
    main()

