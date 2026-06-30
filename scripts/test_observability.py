import json
import uuid
from uuid import UUID

from app.rag.graph_chain import IndustrialGraphRAGChain


def main() -> None:
    session_id = f"observability-test-{uuid.uuid4().hex}"
    result = IndustrialGraphRAGChain().invoke(
        question="轮毂识别异常可能是什么原因？",
        session_id=session_id,
    )

    request_id = result.get("request_id")
    assert request_id, "响应缺少 request_id"
    UUID(request_id)

    metadata = result.get("metadata")
    assert isinstance(metadata, dict), "响应缺少 metadata"

    required_fields = {
        "intent",
        "evidence_score",
        "evidence_enough",
        "retry_count",
        "total_latency_ms",
    }
    missing_fields = required_fields - metadata.keys()
    assert not missing_fields, f"metadata 缺少字段: {sorted(missing_fields)}"
    assert isinstance(
        metadata["total_latency_ms"],
        (int, float),
    ), "total_latency_ms 必须是数值"
    assert metadata["total_latency_ms"] >= 0, "total_latency_ms 不能为负数"

    print(json.dumps(
        {
            "request_id": request_id,
            "session_id": result.get("session_id"),
            "metadata": metadata,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    ))
    print("Observability 验证通过")


if __name__ == "__main__":
    main()
