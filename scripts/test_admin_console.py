"""Integration smoke test for the Phase 5 administration APIs."""

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    if login.status_code != 200:
        raise RuntimeError(
            "管理员登录失败。请先运行 python -m scripts.init_sql_data，"
            f"响应: {login.status_code} {login.text}"
        )

    token = login.json().get("access_token")
    assert token, "登录响应缺少 access_token"
    headers = {"Authorization": f"Bearer {token}"}

    users = client.get("/api/v1/auth/users", headers=headers)
    assert users.status_code == 200, users.text
    assert any(item["username"] == "admin" for item in users.json())

    audit_logs = client.get(
        "/api/v1/audit-logs",
        params={"limit": 10, "offset": 0},
        headers=headers,
    )
    assert audit_logs.status_code == 200, audit_logs.text
    audit_payload = audit_logs.json()
    assert {"items", "total", "limit", "offset"} <= audit_payload.keys()

    audit_stats = client.get("/api/v1/audit-logs/stats", headers=headers)
    assert audit_stats.status_code == 200, audit_stats.text
    assert {
        "total",
        "success_count",
        "denied_count",
        "failed_count",
        "top_actions",
    } <= audit_stats.json().keys()

    anonymous = client.get("/api/v1/audit-logs")
    assert anonymous.status_code == 401, anonymous.text

    readiness = client.get("/health/ready")
    assert readiness.status_code in {200, 503}, readiness.text
    assert {"status", "checks"} <= readiness.json().keys()

    print({
        "status": "success",
        "users": len(users.json()),
        "audit_items_checked": len(audit_payload["items"]),
        "audit_total": audit_payload["total"],
        "readiness": readiness.json()["status"],
    })


if __name__ == "__main__":
    main()
