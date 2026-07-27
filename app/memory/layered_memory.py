from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from threading import BoundedSemaphore
from time import perf_counter
from typing import Any, Callable

from app.core.logger import log_business_event
from app.memory.long_term import LongTermMemoryStore, get_long_term_memory_store
from app.memory.short_term import ShortTermMemoryStore, get_short_term_memory


class LayeredConversationMemory:
    def __init__(
        self,
        *,
        conversation_store: Any,
        short_term_store: ShortTermMemoryStore,
        long_term_store: LongTermMemoryStore,
        submit_task: Callable[[Callable[[], None]], bool],
    ) -> None:
        self.conversation_store = conversation_store
        self.short_term_store = short_term_store
        self.long_term_store = long_term_store
        self.submit_task = submit_task

    def save_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        intent: str | None,
    ) -> None:
        self.conversation_store.save_message(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
        )
        try:
            self.short_term_store.save_message(
                session_id,
                {"role": role, "content": content, "intent": intent},
            )
        except Exception as exc:
            log_business_event(
                "short_term_memory_degraded",
                status="degraded",
                session_id=session_id,
                error_message=str(exc),
            )

    def load_context(
        self,
        *,
        session_id: str,
        owner_key: str,
        query: str,
        recent_limit: int,
        long_term_limit: int,
    ) -> tuple[list[dict], dict]:
        degraded_components = []
        try:
            recent = self.short_term_store.load_messages(
                session_id,
                recent_limit,
            )
            summary = self.short_term_store.load_summary(session_id)
        except Exception as exc:
            degraded_components.append("redis")
            summary = None
            recent = self.conversation_store.load_recent_messages(
                session_id,
                recent_limit,
            )
            log_business_event(
                "short_term_memory_degraded",
                status="degraded",
                session_id=session_id,
                error_message=str(exc),
            )
        if not recent:
            recent = self.conversation_store.load_recent_messages(
                session_id,
                recent_limit,
            )
        try:
            episodic = self.long_term_store.search(
                owner_key=owner_key,
                query=query,
                limit=long_term_limit,
            )
        except Exception as exc:
            degraded_components.append("long_term_memory")
            episodic = []
            log_business_event(
                "long_term_memory_degraded",
                status="degraded",
                session_id=session_id,
                error_message=str(exc),
            )
        messages = []
        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Short-term conversation summary:\n{summary}",
                    "memory_type": "summary",
                }
            )
        messages.extend(
            {
                **item,
                "memory_type": item.get("memory_type", "recent"),
            }
            for item in recent
        )
        messages.extend(
            {
                "role": "memory",
                "content": item.get("content") or item.get("text", ""),
                "intent": item.get("intent"),
                "memory_id": item.get("memory_id"),
                "memory_type": "episodic",
                "score": item.get("score"),
            }
            for item in episodic
        )
        return messages, {
            "memory_mode": "layered",
            "recent_memory_count": len(recent),
            "episodic_memory_count": len(episodic),
            "memory_degraded": bool(degraded_components),
            "memory_degraded_components": degraded_components,
        }

    def save_interaction_async(
        self,
        *,
        owner_key: str,
        session_id: str,
        question: str,
        answer: str,
        intent: str | None,
        request_id: str | None = None,
    ) -> bool:
        if not answer.strip():
            return False

        def task() -> None:
            started_at = perf_counter()
            try:
                memory_id = self.long_term_store.save_interaction(
                    owner_key=owner_key,
                    session_id=session_id,
                    question=question,
                    answer=answer,
                    intent=intent,
                )
                log_business_event(
                    "long_term_memory_indexed",
                    status="success",
                    request_id=request_id,
                    session_id=session_id,
                    memory_id=memory_id,
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
            except Exception as exc:
                log_business_event(
                    "long_term_memory_index_failed",
                    status="failed",
                    request_id=request_id,
                    session_id=session_id,
                    error_message=str(exc),
                    latency_ms=(perf_counter() - started_at) * 1000,
                )

        return self.submit_task(task)


_executor: ThreadPoolExecutor | None = None
_capacity: BoundedSemaphore | None = None


def _submit_background(task: Callable[[], None]) -> bool:
    global _executor, _capacity
    from app.core.config import settings

    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=settings.memory_background_workers,
            thread_name_prefix="long-term-memory",
        )
        _capacity = BoundedSemaphore(settings.memory_background_max_pending)
    assert _capacity is not None
    if not _capacity.acquire(blocking=False):
        log_business_event(
            "long_term_memory_queue_full",
            status="degraded",
            error_message="background memory queue is full",
        )
        return False

    def guarded_task() -> None:
        try:
            task()
        finally:
            _capacity.release()

    _executor.submit(guarded_task)
    return True


@lru_cache(maxsize=1)
def get_layered_conversation_memory() -> LayeredConversationMemory:
    from app.memory.conversation_memory import ConversationMemory

    return LayeredConversationMemory(
        conversation_store=ConversationMemory(),
        short_term_store=get_short_term_memory(),
        long_term_store=get_long_term_memory_store(),
        submit_task=_submit_background,
    )


def shutdown_memory_executor(wait: bool = True) -> None:
    global _executor, _capacity
    if _executor is not None:
        _executor.shutdown(wait=wait, cancel_futures=not wait)
        _executor = None
        _capacity = None
