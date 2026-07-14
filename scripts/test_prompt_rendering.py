from __future__ import annotations

from app.prompting.exceptions import PromptRenderError
from app.prompting.registry import PromptRegistry


def _expect_render_error(callback) -> None:
    try:
        callback()
    except PromptRenderError:
        return
    raise AssertionError("Expected PromptRenderError")


def main() -> None:
    registry = PromptRegistry(
        catalog_path="prompts/catalog",
        release_path="prompts/releases/stable.yaml",
    )

    intent_prompt = registry.render(
        "intent_router",
        {
            "memory_text": "用户: 轮毂识别异常",
            "question": "那优先排查哪个？",
        },
    )
    assert len(intent_prompt.messages) == 2
    assert "那优先排查哪个" in intent_prompt.messages[1].content
    assert intent_prompt.reference.prompt_id == "industrial.intent_router"

    answer_prompt = registry.render(
        "answer_generator",
        {
            "memory_text": "无历史对话。",
            "question": "轮毂识别异常可能是什么原因？",
            "context_text": "摄像头污染可能导致识别置信度下降。",
        },
    )
    assert "摄像头污染" in answer_prompt.messages[1].content
    assert "不可信数据" in answer_prompt.messages[0].content

    _expect_render_error(
        lambda: registry.render(
            "intent_router",
            {"memory_text": "无历史对话。"},
        )
    )
    _expect_render_error(
        lambda: registry.render(
            "intent_router",
            {
                "memory_text": "无历史对话。",
                "question": "测试",
                "unexpected": "禁止输入",
            },
        )
    )
    _expect_render_error(
        lambda: registry.render(
            "intent_router",
            {
                "memory_text": "无历史对话。",
                "question": "x" * 12001,
            },
        )
    )

    print("Strict Prompt rendering test passed")


if __name__ == "__main__":
    main()
