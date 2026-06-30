import json
import uuid

from app.rag.graph_chain import IndustrialGraphRAGChain


def main() -> None:
    session_id = f"memory-test-{uuid.uuid4().hex}"
    chain = IndustrialGraphRAGChain()

    first_result = chain.invoke(
        question="轮毂识别异常可能是什么原因？",
        session_id=session_id,
    )
    print("=" * 80)
    print("第一轮 answer:")
    print(first_result.get("answer", ""))
    print("第一轮 memory_messages:")
    print(json.dumps(
        first_result.get("memory_messages", []),
        ensure_ascii=False,
        indent=2,
        default=str,
    ))

    second_result = chain.invoke(
        question="那优先排查哪个？",
        session_id=session_id,
    )
    print("=" * 80)
    print("第二轮 answer:")
    print(second_result.get("answer", ""))
    second_memory = second_result.get("memory_messages", [])
    assert any(
        message.get("role") == "user"
        and message.get("content") == "轮毂识别异常可能是什么原因？"
        for message in second_memory
    ), "第二轮未加载到第一轮用户消息"
    assert any(
        message.get("role") == "assistant"
        for message in second_memory
    ), "第二轮未加载到第一轮助手消息"

    print("第二轮 memory_messages（应包含第一轮对话）:")
    print(json.dumps(
        second_memory,
        ensure_ascii=False,
        indent=2,
        default=str,
    ))
    print("=" * 80)


if __name__ == "__main__":
    main()
