from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from app.core.logger import log_business_event
from app.evaluation.retrieval_metrics import (
    SUPPORTED_RELEVANCE_FIELDS,
    aggregate_rank_metrics,
    calculate_rank_metrics,
    normalize_identifier,
    normalize_k_values,
    summarize_latency,
)


class RetrievalProtocol(Protocol):
    def retrieve_with_metadata(
        self,
        question: str,
        top_k: int = 5,
    ) -> dict[str, Any]: ...


class RetrievalEvaluator:
    def __init__(self, retriever: RetrievalProtocol | None = None) -> None:
        self._retriever = retriever

    @property
    def retriever(self) -> RetrievalProtocol:
        if self._retriever is None:
            from app.rag.retriever import IndustrialRetriever

            self._retriever = IndustrialRetriever()
        return self._retriever

    @staticmethod
    def load_dataset(path: str | Path) -> list[dict[str, Any]]:
        dataset_path = Path(path)
        if not dataset_path.exists():
            raise FileNotFoundError(
                f"Retrieval evaluation dataset not found: {dataset_path}"
            )
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Retrieval evaluation dataset must be a JSON list")
        RetrievalEvaluator.validate_dataset(payload)
        return payload

    @staticmethod
    def validate_dataset(items: list[dict[str, Any]]) -> None:
        if not items:
            raise ValueError("Retrieval evaluation dataset cannot be empty")
        seen_ids: set[str] = set()
        for index, item in enumerate(items, start=1):
            question_id = str(item.get("id") or "").strip()
            question = str(item.get("question") or "").strip()
            relevance_field = str(
                item.get("relevance_field") or "source"
            ).strip()
            relevant_ids = item.get("relevant_ids")
            if not question_id:
                raise ValueError(f"Dataset item {index} is missing id")
            if question_id in seen_ids:
                raise ValueError(f"Duplicate dataset id: {question_id}")
            seen_ids.add(question_id)
            if not question:
                raise ValueError(f"Dataset item {question_id} is missing question")
            if relevance_field not in SUPPORTED_RELEVANCE_FIELDS:
                raise ValueError(
                    f"Dataset item {question_id} has unsupported "
                    f"relevance_field: {relevance_field}"
                )
            if not isinstance(relevant_ids, list) or not relevant_ids:
                raise ValueError(
                    f"Dataset item {question_id} must define relevant_ids"
                )
            if any(not str(value or "").strip() for value in relevant_ids):
                raise ValueError(
                    f"Dataset item {question_id} contains an empty relevant_id"
                )

    def run(
        self,
        items: list[dict[str, Any]],
        *,
        top_k: int = 5,
        k_values: tuple[int, ...] | list[int] = (1, 3, 5),
        max_questions: int | None = None,
        run_id: str | None = None,
        dataset_name: str | None = None,
    ) -> dict[str, Any]:
        self.validate_dataset(items)
        normalized_k = normalize_k_values(k_values, top_k=top_k)
        if max_questions is not None:
            if max_questions <= 0:
                raise ValueError("max_questions must be greater than zero")
            items = items[:max_questions]

        resolved_run_id = run_id or self._new_run_id()
        started_at = datetime.now(timezone.utc)
        log_business_event(
            "retrieval_evaluation_started",
            status="running",
            run_id=resolved_run_id,
            dataset_name=dataset_name,
            total_questions=len(items),
            top_k=top_k,
            k_values=normalized_k,
        )

        results: list[dict[str, Any]] = []
        for item in items:
            results.append(
                self._evaluate_item(
                    item,
                    top_k=top_k,
                    k_values=normalized_k,
                    run_id=resolved_run_id,
                )
            )

        completed_at = datetime.now(timezone.utc)
        successful = [item for item in results if item["status"] == "success"]
        quality_metrics = aggregate_rank_metrics(
            [item["metrics"] for item in results]
        )
        component_names = (
            "qdrant_latency_ms",
            "opensearch_latency_ms",
            "fusion_latency_ms",
            "reranker_latency_ms",
        )
        component_latency = {
            name: summarize_latency(
                item["latency_breakdown_ms"].get(name, 0.0)
                for item in successful
            )
            for name in component_names
        }
        degraded_count = sum(1 for item in results if item.get("degraded"))
        run_status = (
            "failed"
            if not successful
            else "partial"
            if len(successful) != len(results)
            else "completed"
        )
        report = {
            "run_id": resolved_run_id,
            "status": run_status,
            "dataset_name": dataset_name,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "config": {
                "top_k": top_k,
                "k_values": normalized_k,
                "max_questions": max_questions,
            },
            "summary": {
                "total_questions": len(results),
                "successful_questions": len(successful),
                "failed_questions": len(results) - len(successful),
                "degraded_questions": degraded_count,
                "degraded_rate": (
                    round(degraded_count / len(results), 6) if results else 0.0
                ),
            },
            "metrics": quality_metrics,
            "latency": {
                "retrieval_total": summarize_latency(
                    item["latency_ms"] for item in results
                ),
                "components": component_latency,
            },
            "items": results,
        }
        log_business_event(
            "retrieval_evaluation_completed",
            status=report["status"],
            run_id=resolved_run_id,
            total_questions=len(results),
            successful_questions=len(successful),
            failed_questions=len(results) - len(successful),
            degraded_questions=degraded_count,
            latency_ms=(completed_at - started_at).total_seconds() * 1000,
            metrics=quality_metrics,
        )
        return report

    def _evaluate_item(
        self,
        item: dict[str, Any],
        *,
        top_k: int,
        k_values: list[int],
        run_id: str,
    ) -> dict[str, Any]:
        question_id = str(item["id"])
        question = str(item["question"])
        relevance_field = str(item.get("relevance_field") or "source")
        relevant_ids = [str(value) for value in item["relevant_ids"]]
        started_at = perf_counter()
        try:
            response = self.retriever.retrieve_with_metadata(
                question,
                top_k=top_k,
            )
            latency_ms = (perf_counter() - started_at) * 1000
            contexts = list(response.get("contexts") or [])
            metadata = dict(response.get("metadata") or {})
            metrics = calculate_rank_metrics(
                contexts,
                relevant_ids=relevant_ids,
                relevance_field=relevance_field,
                k_values=k_values,
                top_k=top_k,
            )
            normalized_relevant = {
                normalize_identifier(value, relevance_field)
                for value in relevant_ids
            }
            result = {
                "id": question_id,
                "question": question,
                "status": "success",
                "relevance_field": relevance_field,
                "relevant_ids": relevant_ids,
                "metrics": metrics,
                "latency_ms": round(latency_ms, 2),
                "latency_breakdown_ms": self._latency_breakdown(metadata),
                "retrieval_mode": metadata.get("retrieval_mode", "unknown"),
                "degraded": bool(metadata.get("degraded", False)),
                "degraded_reason": metadata.get("degraded_reason"),
                "ranked_results": [
                    self._summarize_result(
                        context,
                        rank=rank,
                        relevance_field=relevance_field,
                        normalized_relevant=normalized_relevant,
                    )
                    for rank, context in enumerate(contexts, start=1)
                ],
                "error_type": None,
                "error_message": None,
            }
            log_business_event(
                "retrieval_evaluation_item_completed",
                status="success",
                run_id=run_id,
                question_id=question_id,
                latency_ms=latency_ms,
                retrieval_mode=result["retrieval_mode"],
                degraded=result["degraded"],
                metrics=metrics,
            )
            return result
        except Exception as exc:
            latency_ms = (perf_counter() - started_at) * 1000
            zero_metrics = {
                f"{metric}@{k}": 0.0
                for k in k_values
                for metric in ("precision", "recall", "hit_rate", "mrr", "ndcg")
            }
            log_business_event(
                "retrieval_evaluation_item_failed",
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
                "relevance_field": relevance_field,
                "relevant_ids": relevant_ids,
                "metrics": zero_metrics,
                "latency_ms": round(latency_ms, 2),
                "latency_breakdown_ms": self._latency_breakdown({}),
                "retrieval_mode": "unknown",
                "degraded": False,
                "degraded_reason": None,
                "ranked_results": [],
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

    @staticmethod
    def _latency_breakdown(metadata: dict[str, Any]) -> dict[str, float]:
        return {
            name: round(float(metadata.get(name) or 0.0), 2)
            for name in (
                "qdrant_latency_ms",
                "opensearch_latency_ms",
                "fusion_latency_ms",
                "reranker_latency_ms",
            )
        }

    @staticmethod
    def _summarize_result(
        result: dict[str, Any],
        *,
        rank: int,
        relevance_field: str,
        normalized_relevant: set[str],
    ) -> dict[str, Any]:
        identifier = normalize_identifier(
            result.get(relevance_field), relevance_field
        )
        return {
            "rank": rank,
            "doc_id": result.get("doc_id"),
            "chunk_id": result.get("chunk_id"),
            "source": result.get("source"),
            "doc_type": result.get("doc_type"),
            "retrieval_source": result.get("retrieval_source"),
            "score": result.get("score"),
            "rrf_score": result.get("rrf_score"),
            "rerank_score": result.get("rerank_score"),
            "relevant": bool(identifier and identifier in normalized_relevant),
        }

    @staticmethod
    def write_report(report: dict[str, Any], path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_name(
            f".{output_path.name}.{uuid4().hex}.tmp"
        )
        try:
            temporary_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(output_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return output_path

    @staticmethod
    def _new_run_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"retrieval_{timestamp}_{uuid4().hex[:8]}"
