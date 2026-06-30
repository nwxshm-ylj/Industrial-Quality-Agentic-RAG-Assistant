from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.memory.conversation_memory import ConversationMemory


conversation_memory = ConversationMemory()


@observe_node("load_memory")
def load_memory_node(state: IndustrialRAGState) -> dict:
    session_id = state.get("session_id", "default") or "default"
    memory_messages = conversation_memory.load_recent_messages(
        session_id=session_id,
        limit=6,
    )


    return {"memory_messages": memory_messages}
