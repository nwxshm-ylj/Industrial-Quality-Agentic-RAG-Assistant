import logging
from datetime import datetime

from sqlalchemy import text

from app.core.logger import log_security_event, logger
from app.db.session import engine


class AuditService:
    def log_action(
        self,
        request_id: str | None,
        session_id: str | None,
        username: str | None,
        role: str | None,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: str = "success",
        detail: str | None = None,
    ) -> None:
        query = text("""
            INSERT INTO operation_audit_logs (
                request_id, session_id, username, role, action,
                resource_type, resource_id, status, detail
            )
            VALUES (
                :request_id, :session_id, :username, :role, :action,
                :resource_type, :resource_id, :status, :detail
            )
        """)
        try:
            with engine.begin() as conn:
                conn.execute(
                    query,
                    {
                        "request_id": request_id,
                        "session_id": session_id,
                        "username": username,
                        "role": role,
                        "action": action,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "status": status,
                        "detail": detail,
                    },
                )
            log_security_event(
                request_id=request_id,
                username=username,
                role=role,
                action="audit_log_written",
                status="success",
            )
        except Exception as exc:
            logger.log(
                logging.ERROR,
                "audit_log_write_failed",
                extra={
                    "event_data": {
                        "request_id": request_id,
                        "username": username,
                        "role": role,
                        "action": "audit_log_written",
                        "status": "failed",
                        "error_message": str(exc),
                    }
                },
                exc_info=True,
            )

    def list_logs(
        self,
        *,
        username: str | None = None,
        action: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        filters, params = self._build_filters(
            username=username,
            action=action,
            status=status,
            request_id=request_id,
            start_at=start_at,
            end_at=end_at,
        )
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.update({"limit": limit, "offset": offset})
        query = text(f"""
            SELECT
                id, request_id, session_id, username, role, action,
                resource_type, resource_id, status, detail, created_at
            FROM operation_audit_logs
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT :limit OFFSET :offset
        """)
        count_query = text(f"""
            SELECT COUNT(*)
            FROM operation_audit_logs
            {where_clause}
        """)
        with engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
            total = conn.execute(count_query, params).scalar_one()
        return {
            "items": [dict(row) for row in rows],
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }

    def get_stats(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict:
        filters, params = self._build_filters(start_at=start_at, end_at=end_at)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        summary_query = text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE status = 'denied') AS denied_count,
                COUNT(*) FILTER (WHERE status IN ('failed', 'error', 'invalid'))
                    AS failed_count
            FROM operation_audit_logs
            {where_clause}
        """)
        actions_query = text(f"""
            SELECT action, COUNT(*) AS count
            FROM operation_audit_logs
            {where_clause}
            GROUP BY action
            ORDER BY count DESC, action ASC
            LIMIT 8
        """)
        with engine.connect() as conn:
            summary = conn.execute(summary_query, params).mappings().one()
            actions = conn.execute(actions_query, params).mappings().all()
        return {
            **dict(summary),
            "top_actions": [dict(row) for row in actions],
        }

    def _build_filters(
        self,
        *,
        username: str | None = None,
        action: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> tuple[list[str], dict]:
        filters: list[str] = []
        params: dict = {}
        values = {
            "username": username,
            "action": action,
            "status": status,
            "request_id": request_id,
        }
        for field, value in values.items():
            normalized = value.strip() if value else ""
            if normalized:
                filters.append(f"{field} = :{field}")
                params[field] = normalized
        if start_at is not None:
            filters.append("created_at >= :start_at")
            params["start_at"] = start_at
        if end_at is not None:
            filters.append("created_at <= :end_at")
            params["end_at"] = end_at
        return filters, params
