__all__ = ["ConversationMemory"]


def __getattr__(name: str):
    if name == "ConversationMemory":
        from app.memory.conversation_memory import ConversationMemory

        return ConversationMemory
    raise AttributeError(name)
