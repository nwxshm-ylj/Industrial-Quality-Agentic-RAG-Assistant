from app.graph.state import IndustrialRAGState
from app.memory.conversation_memory import ConversationMemory


conversation_memory = ConversationMemory()


def load_memory_node(state: IndustrialRAGState) -> dict:
    session_id = state.get("session_id", "default") or "default"
    memory_messages = conversation_memory.load_recent_messages(
        session_id=session_id,
        limit=6,
    )

    print("=" * 80)
    print("load_memory_node 完成")
    print("session_id:", session_id)
    print("memory_messages 数量:", len(memory_messages))
    print("=" * 80)

    return {"memory_messages": memory_messages}
