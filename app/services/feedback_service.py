import json
from time import perf_counter
from typing import Any

from sqlalchemy import text

from app.core.logger import log_business_event
from app.db.session import engine
from app.services.audit_service import AuditService


VALID_RATINGS = {"positive", "negative", "neutral"}


class FeedbackService:
    def __init__(self) -> None:
        self.audit_service = AuditService()

    @staticmethod
    def _validate_rating(rating: str) -> str:
        normalized = rating.strip().lower()
        if normalized not in VALID_RATINGS:
            raise ValueError(
                "rating 必须是 positive、negative 或 neutral"
            )
        return normalized

    @staticmethod
    def _json_dumps(value: Any) -> str | None:
        if value is None:
            return None
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"JSON 字段无法序列化: {exc}") from exc

    @staticmethod
    def _json_loads(value: str | None) -> Any:
        if not value:
            return None
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None

    def create_feedback(
        self,
        request_id: str | None,
        session_id: str | None,
        username: str | None,
        role: str | None,
        question: str,
        answer: str,
        rating: str,
        comment: str | None = None,
        intent: str | None = None,
        citations: list | dict | None = None,
        metadata: dict | None = None,
    ) -> dict:
        started_at = perf_counter()
        normalized_rating = self._validate_rating(rating)
        if not question.strip():
            raise ValueError("question 不能为空")
        if not answer.strip():
            raise ValueError("answer 不能为空")

        log_business_event(
            "feedback_create_start",
            request_id=request_id,
            session_id=session_id,
            username=username,
            role=role,
            status="started",
        )
        query = text("""
            INSERT INTO answer_feedback (
                request_id, session_id, username, role, question, answer,
                rating, comment, intent, citations, metadata
            )
            VALUES (
                :request_id, :session_id, :username, :role, :question, :answer,
                :rating, :comment, :intent, :citations, :metadata
            )
            RETURNING id, created_at
        """)
        try:
            with engine.begin() as conn:
                row = conn.execute(
                    query,
                    {
                        "request_id": request_id,
                        "session_id": session_id,
                        "username": username,
                        "role": role,
                        "question": question.strip(),
                        "answer": answer.strip(),
                        "rating": normalized_rating,
                        "comment": comment,
                        "intent": intent,
                        "citations": self._json_dumps(citations),
                        "metadata": self._json_dumps(metadata),
                    },
                ).mappings().one()

            latency_ms = (perf_counter() - started_at) * 1000
            self.audit_service.log_action(
                request_id=request_id,
                session_id=session_id,
                username=username,
                role=role,
                action="feedback_create",
                resource_type="answer_feedback",
                resource_id=str(row["id"]),
                status="success",
                detail=f"rating={normalized_rating}; intent={intent}",
            )
            log_business_event(
                "feedback_created",
                request_id=request_id,
                session_id=session_id,
                username=username,
                role=role,
                status="success",
                latency_ms=latency_ms,
                feedback_id=row["id"],
                rating=normalized_rating,
                intent=intent,
            )
            return {
                "id": row["id"],
                "status": "success",
                "message": "反馈已记录",
                "created_at": row["created_at"],
            }
        except Exception as exc:
            latency_ms = (perf_counter() - started_at) * 1000
            self.audit_service.log_action(
                request_id=request_id,
                session_id=session_id,
                username=username,
                role=role,
                action="feedback_create",
                resource_type="answer_feedback",
                status="failed",
                detail=str(exc),
            )
            log_business_event(
                "feedback_error",
                request_id=request_id,
                session_id=session_id,
                username=username,
                role=role,
                status="failed",
                latency_ms=latency_ms,
                error_message=str(exc),
            )
            raise

    def list_feedback(
        self,
        rating: str | None = None,
        username: str | None = None,
        limit: int = 100,
        *,
        actor_username: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
    ) -> list[dict]:
        started_at = perf_counter()
        if limit < 1 or limit > 1000:
            raise ValueError("limit 必须在 1 到 1000 之间")

        filters: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if rating:
            filters.append("rating = :rating")
            params["rating"] = self._validate_rating(rating)
        if username:
            filters.append("username = :username")
            params["username"] = username

        where_clause = (
            "WHERE " + " AND ".join(filters)
            if filters
            else ""
        )
        query = text(f"""
            SELECT
                id, request_id, session_id, username, role, question, answer,
                rating, comment, intent, citations, metadata, created_at
            FROM answer_feedback
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
        """)
        try:
            with engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
            result = []
            for row in rows:
                item = dict(row)
                item["citations"] = self._json_loads(item.get("citations"))
                item["metadata"] = self._json_loads(item.get("metadata"))
                result.append(item)

            latency_ms = (perf_counter() - started_at) * 1000
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=actor_username,
                role=actor_role,
                action="feedback_list_query",
                resource_type="answer_feedback",
                status="success",
                detail=f"rating={rating}; username={username}; count={len(result)}",
            )
            log_business_event(
                "feedback_list_queried",
                request_id=request_id,
                username=actor_username,
                role=actor_role,
                status="success",
                latency_ms=latency_ms,
                result_count=len(result),
            )
            return result
        except Exception as exc:
            log_business_event(
                "feedback_error",
                request_id=request_id,
                username=actor_username,
                role=actor_role,
                status="failed",
                latency_ms=(perf_counter() - started_at) * 1000,
                error_message=str(exc),
            )
            raise

    def get_feedback_stats(
        self,
        *,
        actor_username: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        started_at = perf_counter()
        totals_query = text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE rating = 'positive') AS positive_count,
                COUNT(*) FILTER (WHERE rating = 'negative') AS negative_count,
                COUNT(*) FILTER (WHERE rating = 'neutral') AS neutral_count
            FROM answer_feedback
        """)
        intents_query = text("""
            SELECT COALESCE(NULLIF(intent, ''), 'unknown') AS intent, COUNT(*) AS count
            FROM answer_feedback
            GROUP BY COALESCE(NULLIF(intent, ''), 'unknown')
            ORDER BY count DESC
        """)
        try:
            with engine.connect() as conn:
                totals = dict(conn.execute(totals_query).mappings().one())
                intent_rows = conn.execute(intents_query).mappings().all()

            total = int(totals["total"] or 0)
            positive_count = int(totals["positive_count"] or 0)
            negative_count = int(totals["negative_count"] or 0)
            result = {
                "total": total,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "neutral_count": int(totals["neutral_count"] or 0),
                "positive_rate": round(positive_count / total, 4) if total else 0.0,
                "negative_rate": round(negative_count / total, 4) if total else 0.0,
                "by_intent": {
                    str(row["intent"]): int(row["count"])
                    for row in intent_rows
                },
            }
            latency_ms = (perf_counter() - started_at) * 1000
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=actor_username,
                role=actor_role,
                action="feedback_stats_query",
                resource_type="answer_feedback",
                status="success",
                detail=f"total={total}",
            )
            log_business_event(
                "feedback_stats_queried",
                request_id=request_id,
                username=actor_username,
                role=actor_role,
                status="success",
                latency_ms=latency_ms,
                total=total,
            )
            return result
        except Exception as exc:
            log_business_event(
                "feedback_error",
                request_id=request_id,
                username=actor_username,
                role=actor_role,
                status="failed",
                latency_ms=(perf_counter() - started_at) * 1000,
                error_message=str(exc),
            )
            raise
