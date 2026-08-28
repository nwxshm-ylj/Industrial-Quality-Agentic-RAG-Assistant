from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.core.sensitive_filter import sanitize_telemetry_value


SNAPSHOT_SCHEMA_VERSION = "1.0"
_TEXT_EXCERPT_LIMIT = 1200
_ANSWER_EXCERPT_LIMIT = 2000
_CONTEXT_LIMIT = 20
_DIAGNOSTIC_FIELDS = ("根本原因", "原因", "措施", "对策", "状态", "结果")


def summarize_retrieval_candidates(
    candidates: list[dict[str, Any]],
    *,
    limit: int = _CONTEXT_LIMIT,
) -> list[dict[str, Any]]:
    """Keep only fields needed to explain ranking and evidence selection."""
    return [
        _summarize_context(candidate, rank=rank, capture_content=False)
        for rank, candidate in enumerate(candidates[:limit], start=1)
    ]


def build_diagnostic_snapshot(
    result: dict[str, Any],
    *,
    prompt_release: dict[str, Any] | None = None,
    status: str = "success",
    error_type: str | None = None,
    capture_content: bool | None = None,
    workflow_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if capture_content is None:
        from app.core.config import settings

        capture = settings.telemetry_capture_content
    else:
        capture = capture_content
    retrieval_diagnostics = result.get("retrieval_diagnostics") or {}
    retrieval_metadata = result.get("retrieval_metadata") or {}
    generation_metadata = result.get("generation_context_metadata") or {}
    contexts = list(result.get("contexts") or [])
    generation_contexts = list(result.get("generation_contexts") or [])
    citations = list(result.get("citations") or [])

    snapshot: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "error_type": error_type,
        "content_capture_enabled": capture,
        "routing": {
            "intent": result.get("intent"),
            "task_mode": (result.get("query_features") or {}).get("task_mode"),
            "requested_retrieval_mode": result.get("requested_retrieval_mode"),
            "retrieval_mode": retrieval_metadata.get("retrieval_mode"),
            "query_hash": retrieval_diagnostics.get("query_hash"),
        },
        "retrieval": {
            "metadata": _allowlist(
                retrieval_metadata,
                {
                    "degraded",
                    "degraded_reason",
                    "degraded_components",
                    "fusion_strategy",
                    "vector_result_count",
                    "keyword_result_count",
                    "rerank_candidate_count",
                    "reranker_degraded",
                    "neighbor_added_count",
                    "neighbor_expansion_enabled",
                    "neighbor_expansion_degraded",
                    "neighbor_expansion_reason",
                    "requested_retrieval_mode",
                    "traceability_graph_requested",
                    "traceability_graph_used",
                    "traceability_graph_path_count",
                    "traceability_graph_fallback_reason",
                    "inferred_filter_fallback",
                },
            ),
            "candidates": sanitize_telemetry_value({
                key: value
                for key, value in retrieval_diagnostics.items()
                if isinstance(value, list)
            }),
            "final_contexts": [
                _summarize_context(item, rank=rank, capture_content=capture)
                for rank, item in enumerate(contexts[:_CONTEXT_LIMIT], start=1)
            ],
        },
        "generation": {
            "context_metadata": _allowlist(
                generation_metadata,
                {
                    "input_context_count",
                    "generation_context_count",
                    "generation_context_chars",
                    "generation_context_truncated",
                    "generation_context_max_items",
                    "generation_context_max_chars",
                },
            ),
            "contexts": [
                _summarize_context(item, rank=rank, capture_content=capture)
                for rank, item in enumerate(
                    generation_contexts[:_CONTEXT_LIMIT],
                    start=1,
                )
            ],
            "citations": [
                _summarize_citation(item, rank=rank)
                for rank, item in enumerate(citations[:_CONTEXT_LIMIT], start=1)
            ],
            "answer_excerpt": (
                _text_excerpt(result.get("answer"), _ANSWER_EXCERPT_LIMIT)
                if capture
                else None
            ),
            "evidence_enough": result.get("evidence_enough"),
            "evidence_confidence": result.get("evidence_confidence"),
            "generation_quality_passed": result.get("generation_quality_passed"),
            "answer_abstained": result.get("answer_abstained"),
            "validation": sanitize_telemetry_value(
                result.get("answer_validation") or {}
            ),
        },
        "versions": {
            "prompt_release": (prompt_release or {}).get("release_id"),
            "prompt_versions": (prompt_release or {}).get("versions") or {},
            "embedding_index_version": retrieval_metadata.get(
                "embedding_index_version"
            ),
            "keyword_index_version": retrieval_metadata.get(
                "keyword_index_version"
            ),
        },
        "workflow_events": sanitize_telemetry_value(
            list(workflow_events or [])[-50:]
        ),
    }
    snapshot["checks"] = build_diagnostic_checks(snapshot)
    return sanitize_telemetry_value(snapshot)


def build_diagnostic_checks(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    retrieval = snapshot.get("retrieval") or {}
    generation = snapshot.get("generation") or {}
    metadata = retrieval.get("metadata") or {}
    final_contexts = retrieval.get("final_contexts") or []
    generation_contexts = generation.get("contexts") or []
    citations = generation.get("citations") or []
    checks: list[dict[str, Any]] = []

    if snapshot.get("status") != "success":
        checks.append(
            _check(
                "request_failed",
                "fail",
                "请求执行失败",
                f"执行未完成，错误类型：{snapshot.get('error_type') or 'unknown'}。",
                "runtime",
            )
        )
    elif final_contexts:
        checks.append(
            _check(
                "retrieval_has_context",
                "pass",
                "检索已返回上下文",
                f"最终检索上下文 {len(final_contexts)} 条。",
                "retrieval",
            )
        )
    else:
        checks.append(
            _check(
                "retrieval_has_context",
                "fail",
                "最终检索结果为空",
                "优先检查文档解析、索引、过滤条件和召回服务。",
                "retrieval",
            )
        )

    if metadata.get("degraded"):
        checks.append(
            _check(
                "retrieval_degraded",
                "warning",
                "检索发生降级",
                str(metadata.get("degraded_reason") or "部分检索组件不可用。"),
                "retrieval",
            )
        )
    else:
        checks.append(
            _check(
                "retrieval_degraded",
                "pass",
                "未记录检索降级",
                "候选链路未标记 degraded。",
                "retrieval",
            )
        )

    if final_contexts and not generation_contexts:
        checks.append(
            _check(
                "generation_context_missing",
                "fail",
                "生成上下文为空",
                "检索有结果但没有进入生成上下文，检查上下文预算和筛选逻辑。",
                "context_builder",
            )
        )
    elif len(generation_contexts) < len(final_contexts):
        checks.append(
            _check(
                "generation_context_pruned",
                "warning",
                "部分检索结果未进入生成",
                f"检索 {len(final_contexts)} 条，生成使用 {len(generation_contexts)} 条。",
                "context_builder",
            )
        )
    elif generation_contexts:
        checks.append(
            _check(
                "generation_context_present",
                "pass",
                "生成上下文已建立",
                f"生成使用 {len(generation_contexts)} 条上下文。",
                "context_builder",
            )
        )

    if generation_contexts and not citations:
        checks.append(
            _check(
                "citation_missing",
                "fail",
                "有上下文但无引用",
                "检查引用映射和最终回答整理逻辑。",
                "citation",
            )
        )
    elif citations:
        checks.append(
            _check(
                "citation_present",
                "pass",
                "引用映射已生成",
                f"共 {len(citations)} 条引用。",
                "citation",
            )
        )

    incomplete_bundles = [
        item
        for item in generation_contexts
        if int(item.get("evidence_chunk_count") or 0)
        > len(item.get("evidence_chunk_ids") or [])
    ]
    if incomplete_bundles:
        checks.append(
            _check(
                "evidence_bundle_incomplete",
                "warning",
                "证据包片段记录不完整",
                "evidence_chunk_count 大于已记录的 evidence_chunk_ids 数量。",
                "traceability",
            )
        )

    answer = str(generation.get("answer_excerpt") or "")
    evidence_text = "\n".join(
        str(item.get("text_excerpt") or "") for item in generation_contexts
    )
    if (
        answer
        and evidence_text
        and _has_empty_field_conflict(answer, evidence_text)
    ):
        checks.append(
            _check(
                "possible_empty_field_conflict",
                "warning",
                "回答的空值结论可能与证据冲突",
                "回答声称字段为空，但生成上下文中检测到相同字段的非空结构。请人工核对原文。",
                "generation",
            )
        )

    if not snapshot.get("content_capture_enabled"):
        checks.append(
            _check(
                "historical_content_not_retained",
                "info",
                "历史正文未持久化",
                "当前隐私配置只保存标识、排名和分数；正文对比仅在当前聊天页面可用。",
                "privacy",
            )
        )
    return checks


def build_diagnostics_response(details: dict[str, Any]) -> dict[str, Any]:
    request = details.get("request") or {}
    metadata = request.get("metadata") or {}
    snapshot = (
        metadata.get("diagnostic_snapshot")
        if isinstance(metadata, dict)
        else None
    )
    limitations: list[str] = []
    if not isinstance(snapshot, dict):
        snapshot = None
        limitations.append(
            "该请求产生于诊断快照功能启用前，只能查看既有用量与检索事件。"
        )
    elif not snapshot.get("content_capture_enabled"):
        limitations.append(
            "TELEMETRY_CAPTURE_CONTENT=false，历史快照不包含回答和上下文正文。"
        )
    return {
        "request_id": request.get("request_id"),
        "snapshot_available": snapshot is not None,
        "snapshot": snapshot,
        "checks": list((snapshot or {}).get("checks") or []),
        "request": request,
        "ai_events": details.get("ai_events") or [],
        "retrieval_events": details.get("retrieval_events") or [],
        "limitations": limitations,
    }


def _summarize_context(
    item: dict[str, Any],
    *,
    rank: int,
    capture_content: bool,
) -> dict[str, Any]:
    summary = _allowlist(
        item,
        {
            "doc_id",
            "source",
            "doc_type",
            "chunk_id",
            "chunk_index",
            "page_number",
            "heading_path",
            "retrieval_source",
            "score",
            "vector_score",
            "keyword_score",
            "bm25_score",
            "hybrid_score",
            "rrf_score",
            "weighted_score",
            "rerank_score",
            "final_score_type",
            "adjacent_to_chunk_id",
            "adjacent_distance",
            "traceability_role",
            "evidence_bundle_id",
            "evidence_chunk_ids",
            "evidence_chunk_count",
        },
    )
    summary["rank"] = rank
    summary["text_excerpt"] = (
        _text_excerpt(item.get("text"), _TEXT_EXCERPT_LIMIT)
        if capture_content
        else None
    )
    return sanitize_telemetry_value(summary)


def _summarize_citation(item: dict[str, Any], *, rank: int) -> dict[str, Any]:
    summary = _allowlist(
        item,
        {
            "doc_id",
            "source",
            "doc_type",
            "chunk_id",
            "page_number",
            "retrieval_source",
            "score",
            "final_score_type",
            "evidence_bundle_id",
            "evidence_chunk_ids",
            "evidence_chunk_count",
        },
    )
    summary["rank"] = rank
    return sanitize_telemetry_value(summary)


def _allowlist(payload: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    return {
        key: sanitize_telemetry_value(payload.get(key), key=key)
        for key in keys
        if payload.get(key) is not None
    }


def _text_excerpt(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    if not normalized:
        return None
    return str(sanitize_telemetry_value(normalized))[:limit]


def _has_empty_field_conflict(answer: str, evidence_text: str) -> bool:
    for field in _DIAGNOSTIC_FIELDS:
        empty_pattern = re.compile(
            rf"{re.escape(field)}.{{0,12}}(?:为空|未填写|无记录|未记录)",
            re.IGNORECASE,
        )
        evidence_pattern = re.compile(
            rf"{re.escape(field)}(?:栏)?\s*[:：]\s*"
            rf"(?!为空|未填写|无记录|未记录)\S+",
            re.IGNORECASE,
        )
        if empty_pattern.search(answer) and evidence_pattern.search(evidence_text):
            return True
    return False


def _check(
    code: str,
    status: str,
    title: str,
    detail: str,
    stage: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "status": status,
        "title": title,
        "detail": detail,
        "stage": stage,
    }
