from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.memory.conversation_memory import ConversationMemory


conversation_memory = ConversationMemory()


@observe_node("save_memory")
def save_memory_node(state: IndustrialRAGState) -> dict:
    session_id = state.get("session_id", "default") or "default"
    question = state.get("question", "")
    answer = state.get("answer", "")
    intent = state.get("intent")

    conversation_memory.save_message(
        session_id=session_id,
        role="user",
        content=question,
        intent=intent,
    )

    if answer:
        conversation_memory.save_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            intent=intent,
        )


    return {}
