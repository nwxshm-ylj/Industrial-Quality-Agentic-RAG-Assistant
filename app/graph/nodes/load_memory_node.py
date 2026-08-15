from app.core.config import settings
from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.memory.conversation_memory import ConversationMemory
from app.memory.layered_memory import get_layered_conversation_memory


conversation_memory = ConversationMemory()


@observe_node("load_memory")
def load_memory_node(state: IndustrialRAGState) -> dict:
    if not state.get("memory_enabled", True):
        return {
            "memory_messages": [],
            "memory_metadata": {
                "memory_mode": "disabled_for_evaluation",
                "recent_memory_count": 0,
                "episodic_memory_count": 0,
                "memory_degraded": False,
            },
        }
    session_id = state.get("session_id", "default") or "default"
    if settings.layered_memory_enabled:
        user = state.get("user") or {}
        owner_key = user.get("username") or f"session:{session_id}"
        memory_messages, memory_metadata = (
            get_layered_conversation_memory().load_context(
                session_id=session_id,
                owner_key=owner_key,
                query=state.get("question", ""),
                recent_limit=settings.memory_recent_limit,
                long_term_limit=settings.memory_long_term_limit,
            )
        )
        return {
            "memory_messages": memory_messages,
            "memory_metadata": memory_metadata,
        }
    memory_messages = conversation_memory.load_recent_messages(
        session_id=session_id,
        limit=6,
    )


    return {
        "memory_messages": memory_messages,
        "memory_metadata": {
            "memory_mode": "postgres_recent",
            "recent_memory_count": len(memory_messages),
            "episodic_memory_count": 0,
            "memory_degraded": False,
        },
    }
