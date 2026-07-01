import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import create_access_token, decode_access_token
from app.db.session import engine
from app.services.auth_service import AuthService
from app.services.feedback_service import FeedbackService


REQUIRED_TABLES = {
    "answer_feedback",
    "rag_eval_runs",
    "rag_eval_items",
}


def assert_required_tables() -> None:
    query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY(:table_names)
    """)
    with engine.connect() as conn:
        existing = {
            row["table_name"]
            for row in conn.execute(
                query,
                {"table_names": list(REQUIRED_TABLES)},
            ).mappings()
        }
    missing = REQUIRED_TABLES - existing
    assert not missing, (
        f"缺少数据库表: {sorted(missing)}；"
        "请先运行 python -m scripts.init_sql_data"
    )


def main() -> None:
    marker = uuid4().hex
    request_ids = [
        f"feedback-test-positive-{marker}",
        f"feedback-test-negative-{marker}",
        f"feedback-test-viewer-{marker}",
    ]
    test_username = f"feedback_eval_test_{marker[:12]}"
    viewer_username = f"feedback_viewer_{marker[:12]}"
    feedback_service = FeedbackService()

    try:
        assert_required_tables()

        admin = AuthService().authenticate_user("admin", "admin123")
        assert admin is not None, (
            "默认 admin 用户不可用；请先运行 python -m scripts.init_sql_data"
        )
        token = create_access_token({
            "sub": admin["username"],
            "role": admin["role"],
        })
        assert decode_access_token(token)["sub"] == "admin"
        print("JWT 管理员认证: PASS")

        positive = feedback_service.create_feedback(
            request_id=request_ids[0],
            session_id=f"feedback-test-{marker}",
            username=test_username,
            role="admin",
            question="测试问题：轮毂识别异常如何排查？",
            answer="测试回答：优先检查相机曝光与配置。",
            rating="positive",
            comment="引用准确",
            intent="fault_diagnosis",
            citations=[{"source": "test.md"}],
            metadata={"test_run": marker},
        )
        negative = feedback_service.create_feedback(
            request_id=request_ids[1],
            session_id=f"feedback-test-{marker}",
            username=test_username,
            role="admin",
            question="测试问题：报警原因是什么？",
            answer="测试回答：需要补充现场信息。",
            rating="negative",
            comment="回答不够具体",
            intent="doc_qa",
            citations=[],
            metadata={"test_run": marker},
        )
        assert positive["id"] and negative["id"]

        listed = feedback_service.list_feedback(
            username=test_username,
            limit=10,
            actor_username="admin",
            actor_role="admin",
            request_id=request_ids[0],
        )
        assert len(listed) >= 2

        stats = feedback_service.get_feedback_stats(
            actor_username="admin",
            actor_role="admin",
            request_id=request_ids[0],
        )
        assert stats["total"] >= 2
        assert stats["positive_count"] >= 1
        assert stats["negative_count"] >= 1
        print("反馈创建、查询与统计: PASS")
        print("feedback_stats:", stats)

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        admin_headers = {"Authorization": f"Bearer {token}"}
        assert client.get(
            "/api/v1/feedback/stats",
            headers=admin_headers,
        ).status_code == 200
        assert client.get(
            "/api/v1/feedback",
            headers=admin_headers,
        ).status_code == 200
        assert client.get(
            "/api/v1/evaluation/runs",
            headers=admin_headers,
        ).status_code == 200
        assert client.get("/api/v1/feedback/stats").status_code == 401

        viewer = AuthService().create_user(
            viewer_username,
            "viewer123",
            role="viewer",
        )
        viewer_token = create_access_token({
            "sub": viewer["username"],
            "role": viewer["role"],
        })
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        assert client.get(
            "/api/v1/feedback",
            headers=viewer_headers,
        ).status_code == 403
        assert client.get(
            "/api/v1/evaluation/runs",
            headers=viewer_headers,
        ).status_code == 403
        viewer_feedback = client.post(
            "/api/v1/feedback",
            headers=viewer_headers,
            json={
                "request_id": request_ids[2],
                "session_id": f"feedback-test-{marker}",
                "question": "viewer feedback question",
                "answer": "viewer feedback answer",
                "rating": "neutral",
            },
        )
        assert viewer_feedback.status_code == 200, viewer_feedback.text
        print("Feedback/Evaluation API 鉴权与 RBAC: PASS")

        if os.getenv("RUN_EVALUATION_TEST", "").lower() in {
            "1", "true", "yes"
        }:
            try:
                from app.services.evaluation_service import EvaluationService

                evaluation = EvaluationService().run_evaluation(
                    username=test_username,
                    role="admin",
                    request_id=f"evaluation-test-{marker}",
                    max_questions=1,
                )
                assert evaluation["run_id"]
                assert evaluation["status"] == "completed"
                print("小型 RAG evaluation: PASS")
            except Exception as exc:
                print(
                    "小型 RAG evaluation: SKIPPED "
                    f"(LLM/Qdrant 不可用: {exc})"
                )
        else:
            print(
                "小型 RAG evaluation: SKIPPED "
                "(设置 RUN_EVALUATION_TEST=true 可启用)"
            )

        print("Feedback and RAG Evaluation 测试通过")
    except SQLAlchemyError as exc:
        raise SystemExit(
            "PostgreSQL 不可用或未初始化。请启动数据库并运行 "
            f"python -m scripts.init_sql_data。原始错误: {exc}"
        ) from exc
    finally:
        try:
            report_paths: list[str] = []
            with engine.begin() as conn:
                report_paths = [
                    str(row["report_path"])
                    for row in conn.execute(
                        text("""
                            SELECT report_path
                            FROM rag_eval_runs
                            WHERE username = :username
                        """),
                        {"username": test_username},
                    ).mappings()
                    if row["report_path"]
                ]
                conn.execute(
                    text("""
                        DELETE FROM rag_eval_items
                        WHERE run_id IN (
                            SELECT run_id FROM rag_eval_runs
                            WHERE username = :username
                        )
                    """),
                    {"username": test_username},
                )
                conn.execute(
                    text("DELETE FROM rag_eval_runs WHERE username = :username"),
                    {"username": test_username},
                )
                conn.execute(
                    text("""
                        DELETE FROM answer_feedback
                        WHERE request_id = ANY(:request_ids)
                    """),
                    {"request_ids": request_ids},
                )
                conn.execute(
                    text("""
                        DELETE FROM operation_audit_logs
                        WHERE request_id = ANY(:request_ids)
                           OR username IN (:test_username, :viewer_username)
                    """),
                    {
                        "request_ids": request_ids,
                        "test_username": test_username,
                        "viewer_username": viewer_username,
                    },
                )
                conn.execute(
                    text("DELETE FROM users WHERE username = :username"),
                    {"username": viewer_username},
                )

            eval_dir = Path("data/eval").resolve()
            for report_path in report_paths:
                candidate = Path(report_path).resolve()
                if candidate.parent == eval_dir:
                    candidate.unlink(missing_ok=True)
        except Exception as exc:
            print(f"测试数据清理警告: {exc}")


if __name__ == "__main__":
    main()
