from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


StreamEvent = dict[str, Any]
StreamEventSink = Callable[[StreamEvent], None]


_stream_event_sink: ContextVar[StreamEventSink | None] = ContextVar(
    "industrial_rag_stream_event_sink",
    default=None,
)


NODE_PROGRESS: dict[str, tuple[int, int, str]] = {
    "load_memory": (3, 8, "加载会话记忆"),
    "intent_router": (10, 18, "识别问题意图"),
    "rule_tool": (24, 36, "查询质量规则"),
    "sql_tool": (24, 42, "执行质量数据分析"),
    "query_rewriter": (24, 34, "改写检索问题"),
    "retrieve": (38, 55, "执行混合检索"),
    "evidence_judge": (58, 68, "评估证据充分性"),
    "context_builder": (69, 74, "整理生成上下文"),
    "generate": (75, 86, "生成回答草稿"),
    "answer_verifier": (87, 91, "校验回答引用"),
    "answer_repair": (92, 94, "修复回答引用"),
    "finalize_answer": (95, 96, "确认最终回答"),
    "save_memory": (97, 99, "保存会话记忆"),
}


@contextmanager
def stream_event_sink(sink: StreamEventSink) -> Iterator[None]:
    token = _stream_event_sink.set(sink)
    try:
        yield
    finally:
        _stream_event_sink.reset(token)


def has_stream_event_sink() -> bool:
    return _stream_event_sink.get() is not None


def emit_node_progress(
    *,
    node_name: str,
    status: str,
    state: dict[str, Any],
    latency_ms: float | None = None,
    intent: str | None = None,
    error_message: str | None = None,
) -> None:
    start_progress, completed_progress, label = NODE_PROGRESS.get(
        node_name,
        (0, 0, node_name),
    )
    progress = completed_progress if status == "completed" else start_progress
    if status == "error":
        progress = start_progress

    event: StreamEvent = {
        "event": "progress",
        "node_name": node_name,
        "label": label,
        "status": status,
        "progress": progress,
        "intent": intent if intent is not None else state.get("intent"),
        "retry_count": state.get("retry_count", 0),
    }
    if latency_ms is not None:
        event["latency_ms"] = round(latency_ms, 2)
    if error_message:
        event["error_message"] = error_message
    _emit(event)


def emit_answer_token(delta: str) -> None:
    if delta:
        _emit({"event": "token", "delta": delta})


def emit_answer_replace(answer: str) -> None:
    """Replace any provisional streamed draft with the verified final answer."""
    _emit({"event": "answer_replace", "answer": answer})


def _emit(event: StreamEvent) -> None:
    sink = _stream_event_sink.get()
    if sink is not None:
        sink(event)
