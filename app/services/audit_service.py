import logging

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
