from app.memory.layered_memory import LayeredConversationMemory


class _ConversationStore:
    def __init__(self) -> None:
        self.messages = []

    def save_message(self, session_id, role, content, intent=None):
        self.messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "intent": intent,
            }
        )

    def load_recent_messages(self, session_id, limit=6):
        return [
            item for item in self.messages if item["session_id"] == session_id
        ][-limit:]


class _ShortTermStore:
    def __init__(self, fail_reads=False) -> None:
        self.messages = {}
        self.fail_reads = fail_reads

    def save_message(self, session_id, message):
        self.messages.setdefault(session_id, []).append(message)

    def load_messages(self, session_id, limit):
        if self.fail_reads:
            raise RuntimeError("Redis unavailable")
        return self.messages.get(session_id, [])[-limit:]

    def load_summary(self, session_id):
        if self.fail_reads:
            raise RuntimeError("Redis unavailable")
        return "Earlier wheel-recognition investigation"


class _LongTermStore:
    def __init__(self) -> None:
        self.saved = []

    def save_interaction(self, **kwargs):
        self.saved.append(kwargs)
        return "memory-1"

    def search(self, *, owner_key, query, limit):
        assert owner_key == "engineer-a"
        assert query == "What should I check first?"
        return [
            {
                "memory_id": "memory-old",
                "content": "A prior camera exposure incident was fixed by recalibration.",
                "intent": "fault_diagnosis",
                "score": 0.82,
            }
        ][:limit]


def _submit_immediately(task):
    task()
    return True


def main() -> None:
    conversation = _ConversationStore()
    short_term = _ShortTermStore()
    long_term = _LongTermStore()
    memory = LayeredConversationMemory(
        conversation_store=conversation,
        short_term_store=short_term,
        long_term_store=long_term,
        submit_task=_submit_immediately,
    )
    memory.save_message(
        session_id="s1",
        role="user",
        content="Wheel recognition is abnormal",
        intent="fault_diagnosis",
    )
    messages, metadata = memory.load_context(
        session_id="s1",
        owner_key="engineer-a",
        query="What should I check first?",
        recent_limit=6,
        long_term_limit=4,
    )
    assert any(item.get("memory_type") == "summary" for item in messages)
    assert any(item.get("memory_type") == "recent" for item in messages)
    assert any(item.get("memory_type") == "episodic" for item in messages)
    assert metadata["memory_mode"] == "layered"
    assert metadata["episodic_memory_count"] == 1
    assert metadata["memory_degraded"] is False

    queued = memory.save_interaction_async(
        owner_key="engineer-a",
        session_id="s1",
        question="Wheel recognition is abnormal",
        answer="Check camera exposure first.",
        intent="fault_diagnosis",
        request_id="request-1",
    )
    assert queued is True
    assert long_term.saved[0]["owner_key"] == "engineer-a"

    fallback = LayeredConversationMemory(
        conversation_store=conversation,
        short_term_store=_ShortTermStore(fail_reads=True),
        long_term_store=long_term,
        submit_task=_submit_immediately,
    )
    fallback_messages, fallback_metadata = fallback.load_context(
        session_id="s1",
        owner_key="engineer-a",
        query="What should I check first?",
        recent_limit=6,
        long_term_limit=4,
    )
    assert fallback_messages
    assert "redis" in fallback_metadata["memory_degraded_components"]

    print("Layered memory tests passed with in-memory stores")


if __name__ == "__main__":
    main()
