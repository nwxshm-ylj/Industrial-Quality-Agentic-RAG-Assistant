from app.core.config import settings
from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.memory.conversation_memory import ConversationMemory
from app.memory.layered_memory import get_layered_conversation_memory


conversation_memory = ConversationMemory()


@observe_node("save_memory")
def save_memory_node(state: IndustrialRAGState) -> dict:
    if not state.get("memory_enabled", True):
        return {}
    session_id = state.get("session_id", "default") or "default"
    question = state.get("question", "")
    answer = state.get("answer", "")
    intent = state.get("intent")

    if settings.layered_memory_enabled:
        memory = get_layered_conversation_memory()
        memory.save_message(
            session_id=session_id,
            role="user",
            content=question,
            intent=intent,
        )
        if answer:
            memory.save_message(
                session_id=session_id,
                role="assistant",
                content=answer,
                intent=intent,
            )
            user = state.get("user") or {}
            owner_key = user.get("username") or f"session:{session_id}"
            memory.save_interaction_async(
                owner_key=owner_key,
                session_id=session_id,
                question=question,
                answer=answer,
                intent=intent,
                request_id=state.get("request_id"),
            )
        return {}

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
