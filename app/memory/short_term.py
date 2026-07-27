from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Protocol


class ShortTermMemoryError(RuntimeError):
    pass


class ShortTermMemoryStore(Protocol):
    def save_message(self, session_id: str, message: dict) -> None: ...

    def load_messages(self, session_id: str, limit: int) -> list[dict]: ...

    def load_summary(self, session_id: str) -> str | None: ...


class RedisShortTermMemory:
    def __init__(
        self,
        client: Any,
        *,
        key_prefix: str = "industrial_rag:memory",
        ttl_seconds: int = 86400,
        max_messages: int = 20,
        summary_trigger_messages: int = 12,
        summary_max_chars: int = 1600,
    ) -> None:
        if ttl_seconds <= 0 or max_messages <= 0:
            raise ValueError("Redis memory TTL and max_messages must be positive")
        self.client = client
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds
        self.max_messages = max_messages
        self.summary_trigger_messages = summary_trigger_messages
        self.summary_max_chars = summary_max_chars

    def save_message(self, session_id: str, message: dict) -> None:
        key = self._messages_key(session_id)
        try:
            pipeline = self.client.pipeline()
            pipeline.rpush(key, json.dumps(message, ensure_ascii=False, default=str))
            pipeline.ltrim(key, -self.max_messages, -1)
            pipeline.expire(key, self.ttl_seconds)
            pipeline.execute()
            self._refresh_summary(session_id)
        except Exception as exc:
            raise ShortTermMemoryError(f"Redis memory write failed: {exc}") from exc

    def load_messages(self, session_id: str, limit: int) -> list[dict]:
        if limit <= 0:
            return []
        try:
            values = self.client.lrange(
                self._messages_key(session_id),
                -limit,
                -1,
            )
            return [json.loads(value) for value in values]
        except Exception as exc:
            raise ShortTermMemoryError(f"Redis memory read failed: {exc}") from exc

    def load_summary(self, session_id: str) -> str | None:
        try:
            value = self.client.get(self._summary_key(session_id))
            return str(value) if value else None
        except Exception as exc:
            raise ShortTermMemoryError(f"Redis summary read failed: {exc}") from exc

    def _refresh_summary(self, session_id: str) -> None:
        key = self._messages_key(session_id)
        count = int(self.client.llen(key))
        if count < self.summary_trigger_messages:
            return
        raw_messages = self.client.lrange(
            key,
            0,
            max(0, count - 7),
        )
        messages = [json.loads(value) for value in raw_messages]
        summary = "\n".join(
            f"{message.get('role', 'unknown')}: {message.get('content', '')}"
            for message in messages
        )[-self.summary_max_chars :]
        self.client.setex(
            self._summary_key(session_id),
            self.ttl_seconds,
            summary,
        )

    def _messages_key(self, session_id: str) -> str:
        return f"{self.key_prefix}:session:{session_id}:messages"

    def _summary_key(self, session_id: str) -> str:
        return f"{self.key_prefix}:session:{session_id}:summary"


@lru_cache(maxsize=1)
def get_redis_client() -> Any:
    import redis

    from app.core.config import settings

    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_read_timeout_seconds,
        health_check_interval=30,
    )


@lru_cache(maxsize=1)
def get_short_term_memory() -> RedisShortTermMemory:
    from app.core.config import settings

    return RedisShortTermMemory(
        get_redis_client(),
        key_prefix=settings.memory_redis_key_prefix,
        ttl_seconds=settings.memory_short_term_ttl_seconds,
        max_messages=settings.memory_short_term_max_messages,
        summary_trigger_messages=settings.memory_summary_trigger_messages,
    )
