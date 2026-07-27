from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from time import perf_counter
from typing import Any, Callable, Protocol
from uuid import uuid4

from app.core.logger import log_business_event


RAGAS_METRIC_NAMES = (
    "context_precision",
    "context_recall",
    "response_relevancy",
    "faithfulness",
)


@dataclass(frozen=True)
class SemanticEvaluationSample:
    question_id: str
    user_input: str
    retrieved_contexts: list[str]
    response: str
    reference: str


class SemanticMetricSuite(Protocol):
    suite_name: str
    suite_version: str
    judge_model: str

    def score(
        self,
        sample: SemanticEvaluationSample,
    ) -> dict[str, float]: ...


class RagasMetricSuite:
    """RAGAS v0.4 collections adapter isolated from application services."""

    suite_name = "ragas"

    def __init__(
        self,
        *,
        llm: Any,
        embeddings: Any,
        judge_model: str,
        suite_version: str,
    ) -> None:
        try:
            from ragas.metrics.collections import (
                ContextPrecisionWithReference,
                ContextRecall,
                Faithfulness,
                ResponseRelevancy,
            )
        except ImportError as exc:
            raise RuntimeError(
                "RAGAS is not installed. Install the pinned project dependencies."
            ) from exc

        self.suite_version = suite_version
        self.judge_model = judge_model
        self._metrics = {
            "context_precision": ContextPrecisionWithReference(llm=llm),
            "context_recall": ContextRecall(llm=llm),
            "response_relevancy": ResponseRelevancy(
                llm=llm,
                embeddings=embeddings,
            ),
            "faithfulness": Faithfulness(llm=llm),
        }

    def score(
        self,
        sample: SemanticEvaluationSample,
    ) -> dict[str, float]:
        return asyncio.run(self._score_async(sample))

    async def _score_async(
        self,
        sample: SemanticEvaluationSample,
    ) -> dict[str, float]:
        metric_inputs = {
            "context_precision": {
                "user_input": sample.user_input,
                "retrieved_contexts": sample.retrieved_contexts,
                "reference": sample.reference,
            },
            "context_recall": {
                "user_input": sample.user_input,
                "retrieved_contexts": sample.retrieved_contexts,
                "reference": sample.reference,
            },
            "response_relevancy": {
                "user_input": sample.user_input,
                "response": sample.response,
            },
            "faithfulness": {
                "response": sample.response,
                "retrieved_contexts": sample.retrieved_contexts,
            },
        }
        scores: dict[str, float] = {}
        for name, metric in self._metrics.items():
            result = await metric.ascore(**metric_inputs[name])
            value = getattr(result, "value", result)
            scores[name] = round(float(value), 6)
        return scores


class SemanticRAGEvaluator:
    def __init__(self, metric_suite: SemanticMetricSuite) -> None:
        self.metric_suite = metric_suite

    def run(
        self,
        items: list[dict[str, Any]],
        *,
        result_provider: Callable[[str], dict[str, Any]],
        run_id: str | None = None,
        max_questions: int | None = None,
        dataset_name: str | None = None,
    ) -> dict[str, Any]:
        if not items:
            raise ValueError("RAGAS evaluation dataset cannot be empty")
        if max_questions is not None:
            if max_questions <= 0:
                raise ValueError("max_questions must be greater than zero")
            items = items[:max_questions]

        resolved_run_id = run_id or f"ragas_{uuid4().hex}"
        started_at = perf_counter()
        started_timestamp = datetime.now(timezone.utc)
        log_business_event(
            "ragas_evaluation_started",
            status="running",
            run_id=resolved_run_id,
            dataset_name=dataset_name,
            total_questions=len(items),
            judge_model=self.metric_suite.judge_model,
        )

        results: list[dict[str, Any]] = []
        for item in items:
            results.append(
                self._evaluate_item(
                    item,
                    result_provider=result_provider,
                    run_id=resolved_run_id,
                )
            )

        successful = [item for item in results if item["status"] == "success"]
        metrics = {
            name: round(
                mean(float(item["metrics"][name]) for item in successful),
                6,
            )
            if successful
            else 0.0
            for name in RAGAS_METRIC_NAMES
        }
        status = (
            "failed"
            if not successful
            else "partial"
            if len(successful) != len(results)
            else "completed"
        )
        report = {
            "run_id": resolved_run_id,
            "status": status,
            "dataset_name": dataset_name,
            "framework": self.metric_suite.suite_name,
            "framework_version": self.metric_suite.suite_version,
            "judge_model": self.metric_suite.judge_model,
            "started_at": started_timestamp.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_questions": len(results),
                "successful_questions": len(successful),
                "failed_questions": len(results) - len(successful),
            },
            "metrics": metrics,
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            "items": results,
        }
        log_business_event(
            "ragas_evaluation_completed",
            status=status,
            run_id=resolved_run_id,
            latency_ms=report["latency_ms"],
            metrics=metrics,
            successful_questions=len(successful),
            failed_questions=len(results) - len(successful),
        )
        return report

    def _evaluate_item(
        self,
        item: dict[str, Any],
        *,
        result_provider: Callable[[str], dict[str, Any]],
        run_id: str,
    ) -> dict[str, Any]:
        question_id = str(item.get("id") or "")
        question = str(item.get("question") or "").strip()
        reference = str(item.get("reference_answer") or "").strip()
        if not question_id or not question or not reference:
            raise ValueError(
                "Each RAGAS item requires id, question, and reference_answer"
            )

        started_at = perf_counter()
        try:
            graph_result = result_provider(question)
            contexts = [
                str(context.get("text") or "").strip()
                for context in graph_result.get("contexts", [])
                if str(context.get("text") or "").strip()
            ]
            sample = SemanticEvaluationSample(
                question_id=question_id,
                user_input=question,
                retrieved_contexts=contexts,
                response=str(graph_result.get("answer") or ""),
                reference=reference,
            )
            metrics = self.metric_suite.score(sample)
            missing = set(RAGAS_METRIC_NAMES) - set(metrics)
            if missing:
                raise ValueError(f"Metric suite omitted metrics: {sorted(missing)}")
            result = {
                "id": question_id,
                "question": question,
                "status": "success",
                "reference_answer": reference,
                "response": sample.response,
                "retrieved_context_count": len(contexts),
                "metrics": metrics,
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
                "error_type": None,
                "error_message": None,
            }
            log_business_event(
                "ragas_evaluation_item_completed",
                status="success",
                run_id=run_id,
                question_id=question_id,
                latency_ms=result["latency_ms"],
                metrics=metrics,
            )
            return result
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000, 2)
            log_business_event(
                "ragas_evaluation_item_failed",
                status="failed",
                run_id=run_id,
                question_id=question_id,
                latency_ms=latency_ms,
                error_message=str(exc),
                error_type=type(exc).__name__,
            )
            return {
                "id": question_id,
                "question": question,
                "status": "failed",
                "reference_answer": reference,
                "response": None,
                "retrieved_context_count": 0,
                "metrics": {name: 0.0 for name in RAGAS_METRIC_NAMES},
                "latency_ms": latency_ms,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
