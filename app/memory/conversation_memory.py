from sqlalchemy import text

from app.db.session import engine


class ConversationMemory:
    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: str | None = None,
    ) -> None:
        query = text("""
            INSERT INTO conversation_messages (session_id, role, content, intent)
            VALUES (:session_id, :role, :content, :intent)
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "intent": intent,
                },
            )

    def load_recent_messages(
        self,
        session_id: str,
        limit: int = 6,
    ) -> list[dict]:
        query = text("""
            SELECT id, session_id, role, content, intent, created_at
            FROM conversation_messages
            WHERE session_id = :session_id
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
        """)

        with engine.connect() as conn:
            rows = conn.execute(
                query,
                {
                    "session_id": session_id,
                    "limit": max(int(limit), 0),
                },
            ).mappings().all()

        messages = [dict(row) for row in rows]
        messages.reverse()
        return messages
