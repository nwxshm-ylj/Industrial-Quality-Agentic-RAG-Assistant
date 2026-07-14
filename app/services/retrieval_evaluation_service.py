from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.logger import log_business_event
from app.core.metrics import record_retrieval_evaluation
from app.evaluation.retrieval_evaluator import RetrievalEvaluator
from app.evaluation.retrieval_metrics import normalize_k_values
from app.services.audit_service import AuditService


DEFAULT_DATASET_PATH = Path("data/eval/retrieval_eval_questions.json")
REPORT_NAME_PATTERN = re.compile(r"^retrieval_[A-Za-z0-9_-]{1,90}$")


class RetrievalEvaluationService:
    def __init__(
        self,
        *,
        evaluator: RetrievalEvaluator | None = None,
        report_dir: str | Path = "data/eval",
        audit_service: AuditService | None = None,
    ) -> None:
        self.evaluator = evaluator or RetrievalEvaluator()
        self.report_dir = Path(report_dir)
        self.audit_service = audit_service or AuditService()
        self._restore_latest_metrics()

    def run_evaluation(
        self,
        *,
        username: str,
        role: str,
        request_id: str | None,
        top_k: int = 5,
        k_values: list[int] | tuple[int, ...] = (1, 3, 5),
        max_questions: int | None = None,
    ) -> dict[str, Any]:
        normalized_k = normalize_k_values(k_values, top_k=top_k)
        if max_questions is not None and max_questions <= 0:
            raise ValueError("max_questions must be greater than zero")
        started_at = perf_counter()
        run_id: str | None = None
        try:
            items = self.evaluator.load_dataset(DEFAULT_DATASET_PATH)
            report = self.evaluator.run(
                items,
                top_k=top_k,
                k_values=normalized_k,
                max_questions=max_questions,
                dataset_name=DEFAULT_DATASET_PATH.name,
            )
            run_id = str(report["run_id"])
            report["username"] = username
            report_path = self.report_dir / f"retrieval_eval_report_{run_id}.json"
            report["report_path"] = report_path.as_posix()
            self.evaluator.write_report(report, report_path)
            self.evaluator.write_report(
                report,
                self.report_dir / "retrieval_eval_report.json",
            )
            record_retrieval_evaluation(
                status=report["status"],
                metrics=report["metrics"],
                latency=report["latency"],
            )
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=username,
                role=role,
                action="retrieval_evaluation_run",
                resource_type="retrieval_evaluation",
                resource_id=run_id,
                status=report["status"],
                detail=json.dumps(
                    {
                        "summary": report["summary"],
                        "metrics": report["metrics"],
                    },
                    ensure_ascii=False,
                ),
            )
            log_business_event(
                "retrieval_evaluation_report_saved",
                request_id=request_id,
                username=username,
                role=role,
                status=report["status"],
                run_id=run_id,
                report_path=report_path.as_posix(),
                latency_ms=(perf_counter() - started_at) * 1000,
            )
            return report
        except Exception as exc:
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=username,
                role=role,
                action="retrieval_evaluation_run",
                resource_type="retrieval_evaluation",
                resource_id=run_id,
                status="failed",
                detail=str(exc),
            )
            log_business_event(
                "retrieval_evaluation_failed",
                request_id=request_id,
                username=username,
                role=role,
                status="failed",
                run_id=run_id,
                latency_ms=(perf_counter() - started_at) * 1000,
                error_message=str(exc),
                error_type=type(exc).__name__,
            )
            raise RuntimeError(f"Retrieval evaluation failed: {exc}") from exc

    def list_runs(
        self,
        *,
        limit: int = 50,
        actor_username: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        reports: list[dict[str, Any]] = []
        for path in self.report_dir.glob("retrieval_eval_report_retrieval_*.json"):
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
                report.pop("items", None)
                reports.append(report)
            except (OSError, ValueError, TypeError) as exc:
                log_business_event(
                    "retrieval_evaluation_report_skipped",
                    status="failed",
                    report_path=path.as_posix(),
                    error_message=str(exc),
                    error_type=type(exc).__name__,
                )
        reports.sort(
            key=lambda item: str(item.get("completed_at") or ""),
            reverse=True,
        )
        result = reports[:limit]
        self.audit_service.log_action(
            request_id=request_id,
            session_id=None,
            username=actor_username,
            role=actor_role,
            action="retrieval_evaluation_view",
            resource_type="retrieval_evaluation",
            status="success",
            detail=f"list limit={limit}, returned={len(result)}",
        )
        return result

    def get_run(
        self,
        run_id: str,
        *,
        actor_username: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not REPORT_NAME_PATTERN.fullmatch(run_id):
            raise ValueError("Invalid retrieval evaluation run_id")
        path = self.report_dir / f"retrieval_eval_report_{run_id}.json"
        if not path.exists():
            return None
        report = json.loads(path.read_text(encoding="utf-8"))
        self.audit_service.log_action(
            request_id=request_id,
            session_id=None,
            username=actor_username,
            role=actor_role,
            action="retrieval_evaluation_view",
            resource_type="retrieval_evaluation",
            resource_id=run_id,
            status="success",
        )
        return report

    def _restore_latest_metrics(self) -> None:
        latest_path = self.report_dir / "retrieval_eval_report.json"
        if not latest_path.exists():
            return
        try:
            report = json.loads(latest_path.read_text(encoding="utf-8"))
            record_retrieval_evaluation(
                status=str(report.get("status") or "unknown"),
                metrics=dict(report.get("metrics") or {}),
                latency=dict(report.get("latency") or {}),
                increment_run=False,
            )
        except Exception as exc:
            log_business_event(
                "retrieval_evaluation_metrics_restore_failed",
                status="failed",
                report_path=latest_path.as_posix(),
                error_message=str(exc),
                error_type=type(exc).__name__,
            )
