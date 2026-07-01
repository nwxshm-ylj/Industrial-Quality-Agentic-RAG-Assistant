import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.core.logger import log_business_event
from app.db.session import engine
from app.services.audit_service import AuditService
from scripts.evaluate_system import (
    calculate_metrics,
    evaluate_one,
    load_eval_questions,
)


class EvaluationService:
    def __init__(self) -> None:
        self.audit_service = AuditService()
        self.report_dir = Path("data/eval")

    @staticmethod
    def _json_list(value: Any) -> list:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _parse_json_list(value: str | None) -> list:
        if not value:
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except (TypeError, json.JSONDecodeError):
            return []

    @staticmethod
    def _run_from_row(row: Any) -> dict:
        return dict(row)

    def run_evaluation(
        self,
        username: str | None,
        role: str | None = None,
        request_id: str | None = None,
        max_questions: int | None = None,
    ) -> dict:
        started_at = perf_counter()
        run_id = str(uuid4())
        report_path = self.report_dir / f"eval_report_{run_id}.json"
        log_business_event(
            "evaluation_started",
            request_id=request_id,
            username=username,
            role=role,
            status="started",
            run_id=run_id,
        )

        insert_run = text("""
            INSERT INTO rag_eval_runs (
                run_id, username, status, total_questions, report_path
            )
            VALUES (:run_id, :username, 'running', 0, :report_path)
        """)
        with engine.begin() as conn:
            conn.execute(
                insert_run,
                {
                    "run_id": run_id,
                    "username": username,
                    "report_path": report_path.as_posix(),
                },
            )

        results: list[dict[str, Any]] = []
        try:
            questions = load_eval_questions()
            if max_questions is not None:
                if max_questions < 1:
                    raise ValueError("max_questions 必须大于 0")
                questions = questions[:max_questions]
            if not questions:
                raise ValueError("评估问题集为空")

            insert_item = text("""
                INSERT INTO rag_eval_items (
                    run_id, question_id, question, expected_intent,
                    actual_intent, expected_keywords, keyword_hit,
                    expected_sources, source_hit, answer, latency_ms, passed
                )
                VALUES (
                    :run_id, :question_id, :question, :expected_intent,
                    :actual_intent, :expected_keywords, :keyword_hit,
                    :expected_sources, :source_hit, :answer, :latency_ms, :passed
                )
            """)
            for item in questions:
                item_started_at = perf_counter()
                evaluated = evaluate_one(item)
                results.append(evaluated)

                expected_keywords = self._json_list(
                    item.get("expected_answer_keywords")
                )
                expected_sources = self._json_list(
                    item.get("expected_source_contains")
                )
                latency_ms = float(
                    evaluated.get("latency_ms")
                    or (evaluated.get("latency_seconds") or 0.0) * 1000
                )
                with engine.begin() as conn:
                    conn.execute(
                        insert_item,
                        {
                            "run_id": run_id,
                            "question_id": str(item.get("id") or ""),
                            "question": item["question"],
                            "expected_intent": item.get("expected_intent"),
                            "actual_intent": evaluated.get("actual_intent"),
                            "expected_keywords": json.dumps(
                                expected_keywords,
                                ensure_ascii=False,
                            ),
                            "keyword_hit": bool(
                                evaluated.get("answer_keywords_ok")
                            ),
                            "expected_sources": json.dumps(
                                expected_sources,
                                ensure_ascii=False,
                            ),
                            "source_hit": bool(evaluated.get("source_ok")),
                            "answer": evaluated.get("answer")
                            or evaluated.get("answer_preview"),
                            "latency_ms": latency_ms,
                            "passed": bool(evaluated.get("all_ok")),
                        },
                    )

                log_business_event(
                    "evaluation_item_completed",
                    request_id=request_id,
                    username=username,
                    role=role,
                    status="success",
                    latency_ms=(perf_counter() - item_started_at) * 1000,
                    run_id=run_id,
                    question_id=item.get("id"),
                    passed=bool(evaluated.get("all_ok")),
                )

            metrics = calculate_metrics(results)
            summary = {
                "intent_accuracy": float(metrics.get("intent_accuracy", 0.0)),
                "source_hit_rate": float(
                    metrics.get(
                        "source_hit_rate",
                        metrics.get("source_accuracy", 0.0),
                    )
                ),
                "answer_keyword_hit_rate": float(
                    metrics.get("answer_keyword_hit_rate", 0.0)
                ),
                "memory_followup_success_rate": float(
                    metrics.get("memory_followup_success_rate", 0.0)
                ),
                "avg_latency_ms": float(
                    metrics.get(
                        "avg_latency_ms",
                        (metrics.get("avg_latency_seconds") or 0.0) * 1000,
                    )
                ),
            }
            report = {
                "run_id": run_id,
                "username": username,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {**metrics, **summary},
                "results": results,
            }
            self.report_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            update_run = text("""
                UPDATE rag_eval_runs
                SET
                    status = 'completed',
                    total_questions = :total_questions,
                    intent_accuracy = :intent_accuracy,
                    source_hit_rate = :source_hit_rate,
                    answer_keyword_hit_rate = :answer_keyword_hit_rate,
                    memory_followup_success_rate = :memory_followup_success_rate,
                    avg_latency_ms = :avg_latency_ms,
                    report_path = :report_path
                WHERE run_id = :run_id
            """)
            with engine.begin() as conn:
                conn.execute(
                    update_run,
                    {
                        "run_id": run_id,
                        "total_questions": len(results),
                        "report_path": report_path.as_posix(),
                        **summary,
                    },
                )

            latency_ms = (perf_counter() - started_at) * 1000
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=username,
                role=role,
                action="rag_evaluation_run",
                resource_type="rag_evaluation",
                resource_id=run_id,
                status="success",
                detail=f"total_questions={len(results)}",
            )
            log_business_event(
                "evaluation_completed",
                request_id=request_id,
                username=username,
                role=role,
                status="success",
                latency_ms=latency_ms,
                run_id=run_id,
                total_questions=len(results),
                **summary,
            )
            result = self.get_eval_run(run_id)
            if result is None:
                raise RuntimeError("评估已完成但无法读取运行记录")
            return result
        except Exception as exc:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE rag_eval_runs
                            SET status = 'failed', total_questions = :total_questions
                            WHERE run_id = :run_id
                        """),
                        {
                            "run_id": run_id,
                            "total_questions": len(results),
                        },
                    )
            except Exception:
                pass

            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=username,
                role=role,
                action="rag_evaluation_run",
                resource_type="rag_evaluation",
                resource_id=run_id,
                status="failed",
                detail=str(exc),
            )
            log_business_event(
                "evaluation_failed",
                request_id=request_id,
                username=username,
                role=role,
                status="failed",
                latency_ms=(perf_counter() - started_at) * 1000,
                error_message=str(exc),
                run_id=run_id,
            )
            raise RuntimeError(f"RAG 评估失败: {exc}") from exc

    def list_eval_runs(
        self,
        limit: int = 50,
        *,
        actor_username: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
    ) -> list[dict]:
        if limit < 1 or limit > 200:
            raise ValueError("limit 必须在 1 到 200 之间")
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        run_id, username, status, total_questions,
                        intent_accuracy, source_hit_rate,
                        answer_keyword_hit_rate,
                        memory_followup_success_rate, avg_latency_ms,
                        report_path, created_at
                    FROM rag_eval_runs
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            ).mappings().all()

        self.audit_service.log_action(
            request_id=request_id,
            session_id=None,
            username=actor_username,
            role=actor_role,
            action="rag_evaluation_view",
            resource_type="rag_evaluation",
            status="success",
            detail=f"list_count={len(rows)}",
        )
        return [self._run_from_row(row) for row in rows]

    def get_eval_run(
        self,
        run_id: str,
        *,
        actor_username: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
        audit_view: bool = False,
    ) -> dict | None:
        with engine.connect() as conn:
            run_row = conn.execute(
                text("""
                    SELECT
                        run_id, username, status, total_questions,
                        intent_accuracy, source_hit_rate,
                        answer_keyword_hit_rate,
                        memory_followup_success_rate, avg_latency_ms,
                        report_path, created_at
                    FROM rag_eval_runs
                    WHERE run_id = :run_id
                """),
                {"run_id": run_id},
            ).mappings().first()
            if run_row is None:
                return None

            item_rows = conn.execute(
                text("""
                    SELECT
                        id, run_id, question_id, question, expected_intent,
                        actual_intent, expected_keywords, keyword_hit,
                        expected_sources, source_hit, answer, latency_ms,
                        passed, created_at
                    FROM rag_eval_items
                    WHERE run_id = :run_id
                    ORDER BY id
                """),
                {"run_id": run_id},
            ).mappings().all()

        result = self._run_from_row(run_row)
        items = []
        for row in item_rows:
            item = dict(row)
            item["expected_keywords"] = self._parse_json_list(
                item.get("expected_keywords")
            )
            item["expected_sources"] = self._parse_json_list(
                item.get("expected_sources")
            )
            items.append(item)
        result["items"] = items

        if audit_view:
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=actor_username,
                role=actor_role,
                action="rag_evaluation_view",
                resource_type="rag_evaluation",
                resource_id=run_id,
                status="success",
            )
        return result
