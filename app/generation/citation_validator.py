from __future__ import annotations

import re
from typing import Any


_CITATION_PATTERN = re.compile(r"【资料\s*(\d+)】")
_MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+\S")
_CODE_FENCE = chr(96) * 3
_STRICT_EVIDENCE_MARKERS = (
    "根因",
    "导致",
    "引起",
    "造成",
    "阈值",
    "上限",
    "下限",
    "公差",
    "扭矩",
    "必须",
    "禁止",
    "不得",
    "安全",
    "法规",
    "放行",
)
_ADVICE_MARKERS = ("建议", "应当", "应先", "优先", "检查", "调整", "更换")
_UNCERTAINTY_MARKERS = (
    "可能",
    "或许",
    "不确定",
    "无法确认",
    "资料不足",
    "证据不足",
)


def _available_citations(contexts: list[dict[str, Any]]) -> dict[str, str]:
    available: dict[str, str] = {}
    for index, context in enumerate(contexts, start=1):
        label = str(context.get("citation_label") or f"资料{index}")
        match = _CITATION_PATTERN.search(f"【{label}】")
        if match:
            available[match.group(1)] = label
    return available


def _claim_category(claim_text: str) -> str:
    normalized = re.sub(r"\s+", "", claim_text)
    if any(marker in normalized for marker in _ADVICE_MARKERS):
        return "advice"
    if any(marker in normalized for marker in _UNCERTAINTY_MARKERS):
        return "uncertainty"
    return "fact"


def _claim_evidence_policy(claim_text: str) -> str:
    normalized = re.sub(r"\s+", "", claim_text)
    if re.search(r"\d", normalized) or any(
        marker in normalized for marker in _STRICT_EVIDENCE_MARKERS
    ):
        return "strict"
    return "standard"


def _answer_lines(
    answer: str,
    available: dict[str, str],
) -> list[dict[str, Any]]:
    """Parse Markdown by physical line without extracting semantic claims."""
    lines: list[dict[str, Any]] = []
    in_code_block = False
    for raw_line in answer.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith(_CODE_FENCE):
            in_code_block = not in_code_block
            continue
        if not stripped:
            continue

        line_type = "heading" if _MARKDOWN_HEADING.match(stripped) else "content"
        referenced = list(dict.fromkeys(_CITATION_PATTERN.findall(stripped)))
        valid_ids = [item for item in referenced if item in available]
        invalid_ids = [item for item in referenced if item not in available]
        valid = line_type == "heading" or (
            not in_code_block and bool(valid_ids) and not invalid_ids
        )
        claim_text = _CITATION_PATTERN.sub("", stripped).strip()
        lines.append(
            {
                "type": line_type,
                "text": stripped,
                "referenced_citation_ids": [
                    f"资料{item}" for item in referenced
                ],
                "citation_ids": [f"资料{item}" for item in valid_ids],
                "invalid_citation_ids": [f"资料{item}" for item in invalid_ids],
                "valid": valid,
                "order": len(lines),
                "claim_text": claim_text if line_type == "content" else "",
            }
        )
    return lines


def validate_answer_citations(
    answer: str,
    contexts: list[dict[str, Any]],
    *,
    citation_coverage_threshold: float = 0.8,
    validation_required: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate source labels on each content line.

    The legacy threshold argument is accepted for caller compatibility but is
    intentionally not used as a gate. This validator does not split claims and
    does not perform semantic entailment. For RAG/SQL answers, every non-empty
    non-heading line must carry at least one known source label and may not
    contain an unknown label.
    """
    del citation_coverage_threshold
    available = _available_citations(contexts)
    lines = _answer_lines(answer or "", available)
    content_lines = [item for item in lines if item["type"] == "content"]
    valid_lines = [item for item in content_lines if item["valid"]]
    uncited_lines = [
        item
        for item in content_lines
        if not item["referenced_citation_ids"]
    ]
    invalid_lines = [
        item for item in content_lines if item["invalid_citation_ids"]
    ]
    referenced = _CITATION_PATTERN.findall(answer or "")
    valid_ids = sorted({item for item in referenced if item in available}, key=int)
    invalid_ids = sorted(
        {item for item in referenced if item not in available}, key=int
    )

    line_count = len(content_lines)
    coverage = len(valid_lines) / line_count if line_count else 1.0
    reasons: list[str] = []
    if validation_required:
        if not available:
            reasons.append("no_generation_contexts")
        if invalid_lines:
            reasons.append("invalid_citation_ids")
        if uncited_lines:
            reasons.append("uncited_answer_lines")
        if content_lines and not valid_lines:
            reasons.append("no_valid_citations")
        if not content_lines:
            reasons.append("no_answer_content")

    passed = not reasons
    claims = [
        {
            "text": item["claim_text"],
            "citation_ids": list(item["citation_ids"]),
            "claim_type": "supported" if item["valid"] else "uncited",
            "claim_category": _claim_category(item["claim_text"]),
            "citation_required": True,
            "evidence_policy": _claim_evidence_policy(item["claim_text"]),
            "order": index,
            "line_order": item["order"],
        }
        for index, item in enumerate(content_lines)
    ]
    category_counts = {
        category: sum(1 for claim in claims if claim["claim_category"] == category)
        for category in ("fact", "advice", "uncertainty")
    }
    validation = {
        "passed": passed,
        "citation_contract_passed": passed,
        "validation_required": validation_required,
        "citation_validation_mode": "line_reference_only",
        "citation_coverage": round(coverage, 4),
        "citation_coverage_threshold": None,
        "line_count": line_count,
        "cited_line_count": len(valid_lines),
        "uncited_line_count": len(uncited_lines),
        "invalid_line_count": len(invalid_lines),
        "valid_citation_ids": [f"资料{item}" for item in valid_ids],
        "invalid_citation_ids": [f"资料{item}" for item in invalid_ids],
        "failure_reasons": list(dict.fromkeys(reasons)),
        "semantic_support_checked": False,
        "semantic_support_rate": None,
        "semantic_support_threshold": None,
        "semantic_checked_claim_count": 0,
        "semantic_supported_claim_count": 0,
        "semantic_partial_claim_count": 0,
        "semantic_unsupported_claim_count": 0,
        "semantic_validation_degraded": False,
        "semantic_validation_error": None,
        # Claim metadata is derived from the already enforced physical-line
        # contract. It adds policy propagation without relaxing line checks.
        "claim_count": len(claims),
        "cited_claim_count": len(valid_lines),
        "required_citation_claim_count": len(claims),
        "cited_required_claim_count": len(valid_lines),
        "optional_claim_count": 0,
        "fact_claim_count": category_counts["fact"],
        "advice_claim_count": category_counts["advice"],
        "uncertainty_claim_count": category_counts["uncertainty"],
        "uncited_required_claim_count": len(uncited_lines),
        "uncited_claim_count": len(uncited_lines),
    }
    answer_structure = {
        "summary": next(
            (
                _CITATION_PATTERN.sub("", item["text"]).strip()
                for item in valid_lines
            ),
            "",
        ),
        "claims": claims,
        "missing_information": [],
        "supplementary_advice": [],
        "lines": lines,
    }
    return validation, answer_structure


def apply_semantic_support_validation(
    validation: dict[str, Any],
    answer_structure: dict[str, Any],
    semantic_result: dict[str, Any],
    *,
    support_threshold: float = 1.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge semantic verdicts and make unsupported lines non-releasable."""
    claims = [dict(item) for item in answer_structure.get("claims", [])]
    lines = [dict(item) for item in answer_structure.get("lines", [])]
    verdict_by_index = {
        int(item["claim_index"]): item
        for item in semantic_result.get("claims", [])
        if isinstance(item, dict) and item.get("claim_index") is not None
    }
    supported_count = partial_count = unsupported_count = 0
    semantic_claim_results: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        verdict_item = verdict_by_index.get(index)
        if verdict_item is None:
            continue
        verdict = str(verdict_item.get("verdict") or "unsupported")
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
        line_order = int(claim.get("line_order", -1))
        if 0 <= line_order < len(lines) and verdict != "supported":
            lines[line_order]["valid"] = False
        semantic_claim_results.append(
            {
                "claim_index": index,
                "claim": claim.get("text"),
                "citation_ids": list(claim.get("citation_ids", [])),
                "verdict": verdict,
                "reason": claim["semantic_reason"],
                "evidence_policy": claim.get("evidence_policy", "standard"),
                "claim_category": claim.get("claim_category", "fact"),
                "citation_required": bool(claim.get("citation_required", True)),
            }
        )

    checked_count = len(semantic_claim_results)
    support_rate = supported_count / checked_count if checked_count else 1.0
    reasons = list(validation.get("failure_reasons", []))
    if partial_count:
        reasons.append("semantic_partial_claims")
    if unsupported_count:
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
    return merged_validation, {**answer_structure, "claims": claims, "lines": lines}


def choose_validation_action(
    validation: dict[str, Any],
    *,
    repair_enabled: bool,
    retry_count: int,
    answer_abstained: bool,
) -> str:
    """Choose only finalization or deterministic line pruning."""
    del repair_enabled, retry_count
    if validation.get("passed", False) or answer_abstained:
        return "finalize"
    return "deterministic_prune"


def build_citation_safe_answer(answer_structure: dict[str, Any]) -> str:
    """Keep valid cited content lines and their nearest Markdown headings."""
    output: list[str] = []
    pending_headings: list[str] = []
    for item in answer_structure.get("lines", []):
        if item.get("type") == "heading":
            pending_headings.append(str(item.get("text") or "").strip())
            continue
        if item.get("type") != "content" or not item.get("valid"):
            continue
        for heading in pending_headings:
            if heading and (not output or output[-1] != heading):
                output.append(heading)
        pending_headings.clear()
        text = str(item.get("text") or "").strip()
        if text:
            output.append(text)
    return "\n".join(output)
