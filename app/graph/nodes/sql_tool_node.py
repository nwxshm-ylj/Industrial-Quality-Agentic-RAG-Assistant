from app.core.logger import log_security_event, observe_node
from app.graph.state import IndustrialRAGState
from app.services.audit_service import AuditService
from app.tools.sql_tool import IndustrialSQLTool


sql_tool = IndustrialSQLTool()
audit_service = AuditService()


@observe_node("sql_tool")
def sql_tool_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    user = state.get("user")
    username = user.get("username") if user else None
    role = user.get("role") if user else None
    request_id = state.get("request_id")
    session_id = state.get("session_id")

    if user is not None and role not in {"admin", "engineer"}:
        detail = f"角色 {role} 无权执行 SQL 分析"
        log_security_event(
            request_id=request_id,
            username=username,
            role=role,
            action="permission_denied",
            status="denied",
            error_message=detail,
        )
        audit_service.log_action(
            request_id=request_id,
            session_id=session_id,
            username=username,
            role=role,
            action="permission_denied",
            resource_type="sql_tool",
            status="denied",
            detail=detail,
        )
        audit_service.log_action(
            request_id=request_id,
            session_id=session_id,
            username=username,
            role=role,
            action="sql_tool_execute",
            resource_type="sql_tool",
            status="denied",
            detail=detail,
        )
        raise PermissionError(detail)

    try:
        sql_result = sql_tool.run(question)
        context = sql_tool.format_sql_result_as_context(sql_result)

        citation = {
            "source": context.get("source"),
            "doc_type": context.get("doc_type"),
            "chunk_id": context.get("chunk_id"),
            "score": context.get("score"),
        }


        audit_service.log_action(
            request_id=request_id,
            session_id=session_id,
            username=username,
            role=role,
            action="sql_tool_execute",
            resource_type="sql_tool",
            status="success",
            detail=f"row_count={sql_result.get('row_count', 0)}",
        )

        return {
            "sql_result": sql_result,
            "contexts": [context],
            "citations": [citation],
        }

    except Exception as e:
        audit_service.log_action(
            request_id=request_id,
            session_id=session_id,
            username=username,
            role=role,
            action="sql_tool_execute",
            resource_type="sql_tool",
            status="failed",
            detail=str(e),
        )
        fallback_context = {
            "text": f"SQL查询失败，错误信息：{str(e)}",
            "source": "PostgreSQL",
            "doc_type": "SQL_ERROR",
            "chunk_id": "sql_error",
            "score": 0.0,
        }

        return {
            "sql_result": {
                "question": question,
                "sql": "",
                "rows": [],
                "row_count": 0,
                "error": str(e),
            },
            "contexts": [fallback_context],
            "citations": [
                {
                    "source": "PostgreSQL",
                    "doc_type": "SQL_ERROR",
                    "chunk_id": "sql_error",
                    "score": 0.0,
                }
            ],
        }