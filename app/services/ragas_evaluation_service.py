from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.logger import log_business_event
from app.evaluation.ragas_evaluator import (
    RagasMetricSuite,
    SemanticMetricSuite,
    SemanticRAGEvaluator,
)
from app.evaluation.ragas_compat import install_ragas_langchain_compat
from app.rag.graph_chain import IndustrialGraphRAGChain
from app.services.audit_service import AuditService


RAGAS_RUN_ID_PATTERN = re.compile(r"^ragas_[A-Za-z0-9_-]{1,100}$")


@lru_cache(maxsize=1)
def build_ragas_metric_suite() -> RagasMetricSuite:
    if not settings.ragas_enabled:
        raise RuntimeError(
            "RAGAS evaluation is disabled. Set RAGAS_ENABLED=true explicitly."
        )
    install_ragas_langchain_compat()
    try:
        from openai import AsyncOpenAI
        from ragas.embeddings import OpenAIEmbeddings
        from ragas.llms import llm_factory
    except ImportError as exc:
        raise RuntimeError(
            "RAGAS runtime dependencies are unavailable. Rebuild the API image."
        ) from exc

    judge_client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.ragas_request_timeout_seconds,
        max_retries=settings.ragas_max_retries,
    )
    embedding_client = AsyncOpenAI(
        api_key=settings.qwen_embedding_api_key or settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.ragas_request_timeout_seconds,
        max_retries=settings.ragas_max_retries,
    )
    judge_llm = llm_factory(
        settings.ragas_judge_model,
        provider="openai",
        client=judge_client,
        max_tokens=settings.ragas_judge_max_tokens,
        temperature=0,
        system_prompt=(
            "You evaluate an industrial quality RAG system. Score only from "
            "the supplied question, reference, response, and contexts."
        ),
    )
    embeddings = OpenAIEmbeddings(
        client=embedding_client,
        model=settings.ragas_embedding_model,
    )
    return RagasMetricSuite(
        llm=judge_llm,
        embeddings=embeddings,
        judge_model=settings.ragas_judge_model,
        suite_version=settings.ragas_version,
    )


class RagasEvaluationService:
    def __init__(
        self,
        *,
        metric_suite: SemanticMetricSuite | None = None,
        graph_chain: IndustrialGraphRAGChain | None = None,
        report_dir: str | Path = "data/eval",
        audit_service: AuditService | None = None,
    ) -> None:
        self._metric_suite = metric_suite
        self.graph_chain = graph_chain or IndustrialGraphRAGChain()
        self.report_dir = Path(report_dir)
        self.audit_service = audit_service or AuditService()

    @property
    def metric_suite(self) -> SemanticMetricSuite:
        if self._metric_suite is None:
            self._metric_suite = build_ragas_metric_suite()
        return self._metric_suite

    def run_evaluation(
        self,
        *,
        username: str,
        role: str,
        request_id: str | None,
        max_questions: int | None = None,
        question_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        dataset_path = Path(settings.ragas_dataset_path)
        run_id = f"ragas_{uuid4().hex}"
        try:
            items = json.loads(dataset_path.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                raise ValueError("RAGAS evaluation dataset must be a JSON list")
            if question_ids:
                requested_ids = {str(value).strip() for value in question_ids}
                if "" in requested_ids:
                    raise ValueError("question_ids cannot contain empty values")
                available_ids = {str(item.get("id") or "") for item in items}
                unknown_ids = requested_ids - available_ids
                if unknown_ids:
                    raise ValueError(
                        "Unknown RAGAS question_ids: "
                        + ", ".join(sorted(unknown_ids))
                    )
                items = [
                    item
                    for item in items
                    if str(item.get("id") or "") in requested_ids
                ]
            evaluator = SemanticRAGEvaluator(self.metric_suite)
            report = evaluator.run(
                items,
                result_provider=lambda question: self.graph_chain.invoke(
                    question=question,
                    top_k=5,
                    session_id=f"evaluation-{run_id}-{uuid4().hex}",
                    request_id=str(uuid4()),
                    user={"username": username, "role": role},
                    memory_enabled=False,
                ),
                run_id=run_id,
                max_questions=max_questions,
                dataset_name=dataset_path.name,
            )
            report["username"] = username
            report_path = self.report_dir / f"ragas_eval_report_{run_id}.json"
            report["report_path"] = report_path.as_posix()
            self._write_report(report, report_path)
            self._write_report(
                report,
                self.report_dir / "ragas_eval_report.json",
            )
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=username,
                role=role,
                action="ragas_evaluation_run",
                resource_type="ragas_evaluation",
                resource_id=run_id,
                status=report["status"],
                detail=json.dumps(report["metrics"], ensure_ascii=False),
            )
            return report
        except Exception as exc:
            self.audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=username,
                role=role,
                action="ragas_evaluation_run",
                resource_type="ragas_evaluation",
                resource_id=run_id,
                status="failed",
                detail=str(exc),
            )
            log_business_event(
                "ragas_evaluation_failed",
                request_id=request_id,
                username=username,
                role=role,
                status="failed",
                run_id=run_id,
                latency_ms=(perf_counter() - started_at) * 1000,
                error_message=str(exc),
                error_type=type(exc).__name__,
            )
            raise RuntimeError(f"RAGAS evaluation failed: {exc}") from exc

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        reports = []
        for path in self.report_dir.glob("ragas_eval_report_ragas_*.json"):
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
                report.pop("items", None)
                reports.append(report)
            except (OSError, ValueError, TypeError) as exc:
                log_business_event(
                    "ragas_evaluation_report_skipped",
                    status="failed",
                    report_path=path.as_posix(),
                    error_message=str(exc),
                )
        reports.sort(key=lambda item: str(item.get("run_id") or ""), reverse=True)
        return reports[:limit]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        if not RAGAS_RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("Invalid RAGAS run_id")
        path = self.report_dir / f"ragas_eval_report_{run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_report(report: dict[str, Any], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
