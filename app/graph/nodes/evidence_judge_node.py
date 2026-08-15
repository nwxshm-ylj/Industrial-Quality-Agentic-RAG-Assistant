from __future__ import annotations

import math
import re
from typing import Any

from app.core.config import settings
from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState


_REQUESTED_ASPECTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "原因": (
        ("原因", "根因", "为什么", "为何"),
        ("原因", "根因", "导致", "由于", "失效", "诱因"),
    ),
    "措施": (
        ("措施", "整改", "改进", "怎么处理", "如何处理"),
        ("措施", "整改", "改进", "处理", "对策", "纠正"),
    ),
    "排查步骤": (
        ("排查", "检查步骤", "优先检查", "先查", "如何检查"),
        ("排查", "检查", "确认", "验证", "步骤", "优先"),
    ),
    "风险": (
        ("风险", "影响", "后果", "可能发生"),
        ("风险", "影响", "后果", "危害", "失效"),
    ),
}

_EXPLICIT_UNAVAILABLE_TARGET = re.compile(
    r"(?:未上传|未收录|尚未入库|未入库).{0,8}(?:车型|文档|资料|报告|标准)",
    re.IGNORECASE,
)

_EVIDENCE_LEVEL_HIGH = "HIGH"
_EVIDENCE_LEVEL_MEDIUM = "MEDIUM"
_EVIDENCE_LEVEL_LOW = "LOW"

# Exact limits and safety-critical controls must not be answered from partial
# evidence.  This keeps the relaxed MEDIUM path away from high-risk industrial
# decisions while still allowing partial answers for ordinary diagnosis.
_COMPLETE_EVIDENCE_TERMS = (
    "阈值",
    "上限",
    "下限",
    "公差",
    "扭矩",
    "电压",
    "温度",
    "压力",
    "尺寸",
    "高压",
    "制动",
    "转向",
    "气囊",
    "安全",
    "法规",
    "必须",
    "禁止",
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _raw_score(context: dict[str, Any]) -> float:
    value = context.get("evidence_signal_score")
    if value is None:
        value = context.get("score", 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalized_score(context: dict[str, Any]) -> float:
    """Normalize heterogeneous retrieval scores to a conservative 0..1 signal."""
    score_type = str(context.get("final_score_type") or "").lower()
    if context.get("rerank_score") is not None or score_type == "rerank_score":
        score = float(context.get("rerank_score", _raw_score(context)))
        if 0.0 <= score <= 1.0:
            return score
        return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, score))))
    if score_type == "rrf_score":
        if context.get("vector_score") is not None:
            return _clamp(float(context.get("vector_score") or 0.0))
        return _clamp(float(context.get("rrf_score") or 0.0) / 0.033)
    if score_type == "cross_modal_rrf_score":
        component_scores = [
            float(value)
            for value in (context.get("multimodal_score"), context.get("vector_score"))
            if value is not None
        ]
        if component_scores:
            return _clamp(max(component_scores))
        return _clamp(float(context.get("cross_modal_rrf_score") or 0.0) / 0.033)
    if context.get("vector_score") is not None:
        return _clamp(float(context.get("vector_score") or 0.0))
    return _clamp(_raw_score(context))


def _terms(text: str) -> set[str]:
    normalized = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text.lower()))
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _query_coverage(question: str, contexts: list[dict[str, Any]]) -> float:
    query_terms = _terms(question)
    if not query_terms:
        return 0.0
    context_terms = _terms("\n".join(str(item.get("text") or "") for item in contexts))
    return _clamp(len(query_terms & context_terms) / len(query_terms))


def _missing_aspects(question: str, contexts: list[dict[str, Any]]) -> list[str]:
    evidence_text = "\n".join(str(item.get("text") or "") for item in contexts)
    missing: list[str] = []
    for aspect, (question_terms, evidence_terms) in _REQUESTED_ASPECTS.items():
        if any(term in question for term in question_terms) and not any(
            term in evidence_text for term in evidence_terms
        ):
            missing.append(aspect)
    return missing


def _requires_complete_evidence(question: str) -> bool:
    normalized = str(question or "").lower()
    return any(term in normalized for term in _COMPLETE_EVIDENCE_TERMS)


def _classify_evidence_level(
    *,
    has_contexts: bool,
    evidence_confidence: float,
    missing_aspects: list[str],
    explicit_unavailable_target: bool,
    requires_complete_evidence: bool,
    query_coverage: float,
) -> str:
    """Classify evidence without changing the legacy evidence_enough field.

    HIGH means the requested dimensions are covered with sufficient
    confidence. MEDIUM means the evidence can safely support a bounded partial
    answer. LOW means the system must retry or abstain.
    """
    if not has_contexts or explicit_unavailable_target:
        return _EVIDENCE_LEVEL_LOW

    high_threshold = _clamp(float(settings.evidence_confidence_threshold))
    if evidence_confidence >= high_threshold and not missing_aspects:
        if not requires_complete_evidence or query_coverage >= 0.60:
            return _EVIDENCE_LEVEL_HIGH

    # A relative threshold follows the configured HIGH threshold while the
    # floor prevents very weak retrieval results from becoming answerable.
    medium_threshold = max(0.25, high_threshold * 0.65)
    if (
        evidence_confidence >= medium_threshold
        and not requires_complete_evidence
    ):
        return _EVIDENCE_LEVEL_MEDIUM

    return _EVIDENCE_LEVEL_LOW


@observe_node("evidence_judge")
def evidence_judge_node(state: IndustrialRAGState) -> dict:
    contexts = [
        context
        for context in state.get("contexts", [])
        if str(context.get("text") or "").strip()
        and context.get("doc_type") != "SQL_ERROR"
    ]
    retry_count = state.get("retry_count", 0)
    original_question = state.get("question", "")
    question = state.get("rewritten_query") or original_question
    retrieval_metadata = state.get("retrieval_metadata", {})
    explicit_unavailable_target = bool(
        _EXPLICIT_UNAVAILABLE_TARGET.search(f"{original_question}\n{question}")
    )

    scored_contexts = [
        context for context in contexts if context.get("doc_type") != "KNOWLEDGE_GRAPH"
    ]
    coverage = 0.0

    if not scored_contexts:
        evidence_score = 0.0
        evidence_confidence = 0.0
        missing_aspects = _missing_aspects(question, scored_contexts)
        evidence_reasons = ["未检索到可用于回答的文档证据"]
    else:
        raw_scores = [_raw_score(context) for context in scored_contexts]
        normalized_scores = [_normalized_score(context) for context in scored_contexts]
        evidence_score = max(raw_scores)
        best_quality = max(normalized_scores)
        coverage = _query_coverage(question, scored_contexts)
        unique_support = {
            str(context.get("chunk_id") or context.get("text"))
            for context in scored_contexts
        }
        support = min(1.0, len(unique_support) / 2.0)
        missing_aspects = _missing_aspects(question, scored_contexts)
        degraded = bool(retrieval_metadata.get("degraded", False))
        evidence_confidence = round(
            _clamp(
                0.55 * best_quality
                + 0.25 * coverage
                + 0.20 * support
                - 0.08 * len(missing_aspects)
                - (0.10 if degraded else 0.0)
            ),
            4,
        )
        evidence_reasons = [
            f"最高检索质量归一化分数={best_quality:.3f}",
            f"问题与证据词面覆盖率={coverage:.3f}",
            f"独立证据数量={len(unique_support)}",
        ]
        if missing_aspects:
            evidence_reasons.append(
                "缺少问题要求的证据维度：" + "、".join(missing_aspects)
            )
        if degraded:
            reason = retrieval_metadata.get("degraded_reason") or "检索组件降级"
            evidence_reasons.append(f"检索处于降级状态：{reason}")

    if explicit_unavailable_target:
        if "目标对象资料未入库" not in missing_aspects:
            missing_aspects.append("目标对象资料未入库")
        evidence_reasons.append("问题明确指出目标车型或资料尚未入库")

    requires_complete_evidence = _requires_complete_evidence(
        f"{original_question}\n{question}"
    )
    evidence_level = _classify_evidence_level(
        has_contexts=bool(scored_contexts),
        evidence_confidence=evidence_confidence,
        missing_aspects=missing_aspects,
        explicit_unavailable_target=explicit_unavailable_target,
        requires_complete_evidence=requires_complete_evidence,
        query_coverage=coverage,
    )
    partial_answer_allowed = evidence_level == _EVIDENCE_LEVEL_MEDIUM

    # Backward compatibility: downstream nodes continue to consume the
    # existing boolean. HIGH and MEDIUM are answerable; LOW keeps the original
    # retry/abstention behavior.
    evidence_enough = evidence_level in {
        _EVIDENCE_LEVEL_HIGH,
        _EVIDENCE_LEVEL_MEDIUM,
    }
    evidence_reasons.append(f"证据等级={evidence_level}")
    if partial_answer_allowed:
        evidence_reasons.append("现有证据仅支持部分回答，缺失维度必须明确说明")

    retrieval_metadata = {
        **retrieval_metadata,
        "evidence_level": evidence_level,
        "partial_answer_allowed": partial_answer_allowed,
        "requires_complete_evidence": requires_complete_evidence,
        "evidence_query_coverage": round(coverage, 4),
    }
    abstain_reason = None
    if not evidence_enough:
        if explicit_unavailable_target:
            abstain_reason = "问题所指的目标车型或资料明确尚未上传到知识库"
        elif not scored_contexts:
            abstain_reason = "未检索到足够的知识库证据"
        elif missing_aspects:
            abstain_reason = "现有资料缺少以下关键维度：" + "、".join(missing_aspects)
        else:
            abstain_reason = (
                f"证据可信度不足：{evidence_confidence:.3f} < "
                f"{settings.evidence_confidence_threshold:.3f}"
            )
        retry_count += 1

    return {
        "evidence_score": evidence_score,
        "evidence_enough": evidence_enough,
        "evidence_confidence": evidence_confidence,
        "evidence_reasons": evidence_reasons,
        "missing_aspects": missing_aspects,
        "abstain_reason": abstain_reason,
        "retrieval_metadata": retrieval_metadata,
        "retry_count": retry_count,
    }


def route_after_evidence_judge(state: IndustrialRAGState) -> str:
    if state.get("evidence_enough", False):
        return "generate"
    if state.get("retry_count", 0) <= 1:
        return "rewrite"
    return "generate"
