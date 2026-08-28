from app.streaming.events import (
    emit_answer_replace,
    emit_answer_token,
    emit_node_progress,
    stream_event_sink,
)


def main() -> None:
    events: list[dict] = []
    state = {
        "request_id": "stream-test-request",
        "session_id": "stream-test-session",
        "intent": "doc_qa",
        "retry_count": 0,
    }

    with stream_event_sink(events.append):
        emit_node_progress(
            node_name="retrieve",
            status="running",
            state=state,
        )
        emit_node_progress(
            node_name="retrieve",
            status="completed",
            state=state,
            latency_ms=123.45,
        )
        emit_answer_token("优先检查相机")
        emit_answer_replace("优先检查相机【资料1】。")

    assert [event["event"] for event in events] == [
        "progress",
        "progress",
        "token",
        "answer_replace",
    ]
    assert events[0]["progress"] == 38
    assert events[1]["progress"] == 55
    assert events[1]["latency_ms"] == 123.45
    assert events[2]["delta"] == "优先检查相机"
    assert events[3]["answer"] == "优先检查相机【资料1】。"
    print("Streaming event contract test passed")


if __name__ == "__main__":
    main()
