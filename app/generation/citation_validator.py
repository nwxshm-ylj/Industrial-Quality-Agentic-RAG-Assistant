from __future__ import annotations

import re
from typing import Any


_CITATION_PATTERN = re.compile(r"【资料\s*(\d+)】")
_MARKDOWN_PREFIX = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)、]\s*)")
_NON_FACTUAL_PREFIXES = (
    "补充建议",
    "信息缺口",
    "未覆盖内容",
    "请补充",
    "暂时无法",
    "根据当前检索到的资料",
)

_DETERMINISTIC_PRUNING_REASONS = {
    "citation_coverage_below_threshold",
}

_UNCERTAINTY_MARKERS = (
    "可能",
    "或许",
    "不确定",
    "无法确认",
    "无法判断",
    "资料不足",
    "信息不足",
    "证据不足",
    "尚不能",
    "暂不能",
)
_FACTUAL_SIGNAL_MARKERS = (
    "导致",
    "引起",
    "造成",
    "原因",
    "说明",
    "表明",
    "阈值为",
    "标准为",
    "要求为",
    "规定为",
)
_OPERATIONAL_ADVICE_MARKERS = (
    "检查",
    "调整",
    "更换",
    "校准",
    "停机",
    "返工",
    "隔离",
    "拆卸",
    "测量",
    "验证",
    "放行",
)
_GENERIC_ADVICE_MARKERS = (
    "补充资料",
    "补充信息",
    "咨询负责人",
    "咨询相关人员",
    "查看原始文件",
    "查阅原始文件",
    "进一步确认",
    "人工确认",
)
_ADVICE_MARKERS = (
    "建议",
    "应当",
    "应先",
    "优先",
)


def _available_citations(contexts: list[dict[str, Any]]) -> dict[str, str]:
    available: dict[str, str] = {}
    for index, context in enumerate(contexts, start=1):
        label = str(context.get("citation_label") or f"资料{index}")
        match = _CITATION_PATTERN.search(f"【{label}】")
        if match:
            available[match.group(1)] = label
    return available


def _claim_lines(answer: str) -> list[str]:
    claims: list[str] = []
    in_code_block = False
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line or line.startswith(("#", ">")):
            continue
        line = _MARKDOWN_PREFIX.sub("", line).strip()
        if not line or line.endswith("："):
            continue
        plain = _CITATION_PATTERN.sub("", line).strip(" 。；：")
        if len(plain) < 4:
            continue
        claims.append(line)
    return claims


def _classify_claim(claim_text: str) -> tuple[str, bool]:
    """Classify a claim and decide whether it must carry a citation.

    Facts and concrete industrial actions require evidence. Pure uncertainty
    disclosures and generic process advice do not. A hedged factual statement
    still requires evidence when it contains a causal or numeric assertion.
    """
    normalized = re.sub(r"\s+", "", claim_text)
    has_uncertainty = any(marker in normalized for marker in _UNCERTAINTY_MARKERS)
    has_factual_signal = bool(re.search(r"\d", normalized)) or any(
        marker in normalized for marker in _FACTUAL_SIGNAL_MARKERS
    )

    if any(marker in normalized for marker in _OPERATIONAL_ADVICE_MARKERS):
        return "advice", True
    if has_uncertainty:
        return "uncertainty", has_factual_signal
    if normalized.startswith(_NON_FACTUAL_PREFIXES) or any(
        marker in normalized for marker in _GENERIC_ADVICE_MARKERS
    ):
        return "advice", False
    if any(marker in normalized for marker in _ADVICE_MARKERS):
        return "advice", True
    return "fact", True


def validate_answer_citations(
    answer: str,
    contexts: list[dict[str, Any]],
    *,
    citation_coverage_threshold: float = 0.8,
    validation_required: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the citation contract without pretending to do NLI.

    This validator proves that generated claims use known citation labels and
    measures citation coverage. It deliberately does not claim semantic
    entailment between a claim and the cited chunk.
    """
    available = _available_citations(contexts)
    referenced = _CITATION_PATTERN.findall(answer or "")
    valid_ids = sorted({item for item in referenced if item in available}, key=int)
    invalid_ids = sorted({item for item in referenced if item not in available}, key=int)
    claim_lines = _claim_lines(answer or "")

    structured_claims: list[dict[str, Any]] = []
    cited_claim_count = 0
    cited_required_claim_count = 0
    required_citation_claim_count = 0
    category_counts = {"fact": 0, "advice": 0, "uncertainty": 0}
    uncited_claims: list[str] = []
    uncited_required_claims: list[str] = []
    supplementary_advice: list[str] = []
    for line in claim_lines:
        ids = _CITATION_PATTERN.findall(line)
        claim_valid_ids = [item for item in ids if item in available]
        claim_text = _CITATION_PATTERN.sub("", line).strip()
        claim_category, citation_required = _classify_claim(claim_text)
        category_counts[claim_category] += 1
        if citation_required:
            required_citation_claim_count += 1
        if claim_valid_ids:
            cited_claim_count += 1
            if citation_required:
                cited_required_claim_count += 1
        else:
            uncited_claims.append(claim_text)
            if citation_required:
                uncited_required_claims.append(claim_text)
        if claim_category == "advice":
            supplementary_advice.append(claim_text)
        structured_claims.append(
            {
                "text": claim_text,
                "citation_ids": [f"资料{item}" for item in claim_valid_ids],
                "claim_type": (
                    "supported"
                    if claim_valid_ids
                    else "uncited"
                    if citation_required
                    else claim_category
                ),
                "claim_category": claim_category,
                "citation_required": citation_required,
            }
        )

    total_claims = len(claim_lines)
    coverage = (
        cited_required_claim_count / required_citation_claim_count
        if required_citation_claim_count
        else 1.0
    )
    reasons: list[str] = []
    if validation_required and not available:
        reasons.append("no_generation_contexts")
    if invalid_ids:
        reasons.append("invalid_citation_ids")
    if validation_required and required_citation_claim_count and not cited_required_claim_count:
        reasons.append("no_valid_citations")
    if validation_required and coverage < citation_coverage_threshold:
        reasons.append("citation_coverage_below_threshold")

    passed = not reasons
    validation = {
        "passed": passed,
        "citation_contract_passed": passed,
        "validation_required": validation_required,
        "citation_coverage": round(coverage, 4),
        "citation_coverage_threshold": citation_coverage_threshold,
        "claim_count": total_claims,
        "cited_claim_count": cited_claim_count,
        "required_citation_claim_count": required_citation_claim_count,
        "cited_required_claim_count": cited_required_claim_count,
        "optional_claim_count": total_claims - required_citation_claim_count,
        "fact_claim_count": category_counts["fact"],
        "advice_claim_count": category_counts["advice"],
        "uncertainty_claim_count": category_counts["uncertainty"],
        "uncited_required_claim_count": len(uncited_required_claims),
        "valid_citation_ids": [f"资料{item}" for item in valid_ids],
        "invalid_citation_ids": [f"资料{item}" for item in invalid_ids],
        "uncited_claim_count": len(uncited_claims),
        "failure_reasons": reasons,
        "semantic_support_checked": False,
    }
    answer_structure = {
        "summary": structured_claims[0]["text"] if structured_claims else "",
        "claims": structured_claims,
        "missing_information": [],
        "supplementary_advice": supplementary_advice,
    }
    return validation, answer_structure


def choose_validation_action(
    validation: dict[str, Any],
    *,
    repair_enabled: bool,
    retry_count: int,
    answer_abstained: bool,
) -> str:
    """Choose the cheapest safe action after answer validation.

    Citation coverage alone is a deterministic formatting problem: cited and
    semantically supported claims can be retained without another generation
    call. Missing/invalid citations and semantic support failures still need
    the single LLM repair attempt. After that attempt, finalization performs a
    conservative prune or refusal.
    """
    if validation.get("passed", False):
        return "finalize"
    if answer_abstained:
        return "finalize"

    reasons = set(validation.get("failure_reasons", []))
    if reasons and reasons.issubset(_DETERMINISTIC_PRUNING_REASONS):
        return "deterministic_prune"
    if repair_enabled and retry_count < 1:
        return "llm_repair"
    return "finalize"


def apply_semantic_support_validation(
    validation: dict[str, Any],
    answer_structure: dict[str, Any],
    semantic_result: dict[str, Any],
    *,
    support_threshold: float = 1.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge semantic claim/evidence verdicts into deterministic validation."""
    claims = [dict(item) for item in answer_structure.get("claims", [])]
    verdict_by_index = {
        int(item["claim_index"]): item
        for item in semantic_result.get("claims", [])
        if isinstance(item, dict) and item.get("claim_index") is not None
    }
    checked_count = supported_count = partial_count = unsupported_count = 0
    semantic_claim_results: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        verdict_item = verdict_by_index.get(index)
        if verdict_item is None:
            continue
        verdict = str(verdict_item.get("verdict") or "unsupported")
        checked_count += 1
        if verdict == "supported":
            supported_count += 1
            claim["claim_type"] = "supported"
        elif verdict == "partial":
            partial_count += 1
            claim["claim_type"] = "partial"
        else:
            unsupported_count += 1
            claim["claim_type"] = "unsupported"
        claim["semantic_verdict"] = verdict
        claim["semantic_reason"] = str(verdict_item.get("reason") or "")
        semantic_claim_results.append(
            {
                "claim_index": index,
                "claim": claim.get("text"),
                "citation_ids": list(claim.get("citation_ids", [])),
                "verdict": verdict,
                "reason": claim["semantic_reason"],
            }
        )

    support_rate = supported_count / checked_count if checked_count else 1.0
    reasons = list(validation.get("failure_reasons", []))
    if checked_count and (partial_count or unsupported_count):
        reasons.append("semantic_unsupported_claims")
    if checked_count and support_rate < support_threshold:
        reasons.append("semantic_support_below_threshold")
    reasons = list(dict.fromkeys(reasons))

    merged_validation = {
        **validation,
        "passed": not reasons,
        "failure_reasons": reasons,
        "semantic_support_checked": True,
        "semantic_support_rate": round(support_rate, 4),
        "semantic_support_threshold": support_threshold,
        "semantic_checked_claim_count": checked_count,
        "semantic_supported_claim_count": supported_count,
        "semantic_partial_claim_count": partial_count,
        "semantic_unsupported_claim_count": unsupported_count,
        "semantic_claim_results": semantic_claim_results,
        "semantic_validation_degraded": False,
        "semantic_validation_error": None,
    }
    merged_structure = {**answer_structure, "claims": claims}
    return merged_validation, merged_structure


def build_citation_safe_answer(answer_structure: dict[str, Any]) -> str:
    """Build a conservative answer containing only claims with known citations."""
    lines: list[str] = []
    for claim in answer_structure.get("claims", []):
        if claim.get("claim_type") != "supported":
            continue
        text = str(claim.get("text") or "").strip()
        citation_ids = [
            str(value) for value in claim.get("citation_ids", []) if value
        ]
        if not text or not citation_ids:
            continue
        citations = "".join(f"【{value}】" for value in citation_ids)
        lines.append(f"- {text} {citations}")
    return "\n".join(lines)
