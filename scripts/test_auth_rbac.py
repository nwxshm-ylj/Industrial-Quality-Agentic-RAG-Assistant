import json

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import engine
from app.graph.nodes.sql_tool_node import sql_tool_node
from app.main import app
from app.services.auth_service import AuthService


TEST_VIEWER_USERNAME = "rbac_viewer_test"
TEST_VIEWER_PASSWORD = "viewer123"


def main() -> None:
    auth_service = AuthService()

    try:
        with engine.connect() as conn:
            admin_row = conn.execute(
                text("""
                    SELECT username, password_hash, role, is_active
                    FROM users
                    WHERE username = 'admin'
                """)
            ).mappings().first()
    except Exception as exc:
        raise RuntimeError(
            "认证数据表不可用，请先运行 python -m scripts.init_sql_data"
        ) from exc

    assert admin_row is not None, "默认 admin 用户不存在"
    assert admin_row["password_hash"] != "admin123", "admin 密码被明文保存"
    assert admin_row["role"] == "admin"
    assert admin_row["is_active"] is True
    assert auth_service.authenticate_user("admin", "admin123") is not None

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": TEST_VIEWER_USERNAME},
        )

    client = TestClient(app)
    try:
        no_token_documents = client.get("/api/v1/documents")
        assert no_token_documents.status_code == 401

        no_token_graph = client.post(
            "/api/v1/graph-chat",
            json={"question": "你是谁？"},
        )
        assert no_token_graph.status_code == 401

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert admin_login.status_code == 200, admin_login.text
        admin_payload = admin_login.json()
        admin_token = admin_payload.get("access_token")
        assert admin_token, "登录响应缺少 access_token"
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        admin_documents = client.get(
            "/api/v1/documents",
            headers=admin_headers,
        )
        assert admin_documents.status_code == 200, admin_documents.text

        create_viewer = client.post(
            "/api/v1/auth/users",
            headers=admin_headers,
            json={
                "username": TEST_VIEWER_USERNAME,
                "password": TEST_VIEWER_PASSWORD,
                "role": "viewer",
            },
        )
        assert create_viewer.status_code == 200, create_viewer.text

        viewer_login = client.post(
            "/api/v1/auth/login",
            json={
                "username": TEST_VIEWER_USERNAME,
                "password": TEST_VIEWER_PASSWORD,
            },
        )
        assert viewer_login.status_code == 200, viewer_login.text
        viewer_token = viewer_login.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        viewer_documents = client.get(
            "/api/v1/documents",
            headers=viewer_headers,
        )
        assert viewer_documents.status_code == 200

        viewer_delete = client.delete(
            "/api/v1/documents/nonexistent-doc",
            headers=viewer_headers,
        )
        assert viewer_delete.status_code == 403

        viewer_state = {
            "question": "最近一周质量问题数量是多少？",
            "request_id": "rbac-sql-test",
            "session_id": "rbac-test-session",
            "user": {
                "username": TEST_VIEWER_USERNAME,
                "role": "viewer",
            },
            "intent": "sql_analysis",
        }
        try:
            sql_tool_node(viewer_state)
        except PermissionError:
            pass
        else:
            raise AssertionError("viewer 未被 SQL Tool 拒绝")

        with engine.connect() as conn:
            audit_count = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM operation_audit_logs
                    WHERE action IN (
                        'login_success',
                        'permission_denied',
                        'sql_tool_execute'
                    )
                """)
            ).scalar_one()
        assert audit_count > 0, "未写入操作审计日志"

        print(json.dumps(
            {
                "admin_login": admin_payload["user"],
                "admin_documents_status": admin_documents.status_code,
                "viewer_documents_status": viewer_documents.status_code,
                "viewer_delete_status": viewer_delete.status_code,
                "no_token_status": no_token_documents.status_code,
                "audit_count": audit_count,
            },
            ensure_ascii=False,
            indent=2,
        ))
        print("Authentication and RBAC 验证通过")

    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM users WHERE username = :username"),
                {"username": TEST_VIEWER_USERNAME},
            )


if __name__ == "__main__":
    main()
