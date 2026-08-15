from __future__ import annotations

import re


_ABSTENTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:当前|现有|提供的)?(?:知识库|参考资料|资料).{0,20}(?:未发现|未提供|未提及|没有).{0,80}(?:信息|内容|证据|标准|数据|记录)",
        r"未发现.{0,30}(?:任何信息|相关信息|相关内容|相关记录)",
        r"(?:暂时|目前|当前).{0,12}无法(?:可靠)?(?:确认|回答|判断)",
        r"无法从(?:当前|现有|提供的)?(?:知识库|参考资料|资料).{0,12}(?:确认|得出|回答)",
    )
)

_ABSENCE_CLAIM = re.compile(
    r"(?:不含|未包含|不包括|未提及|未涉及|不涉及|未提供|没有).{0,24}(?:内容|信息|证据|标准|数据|记录|高压电池|热失控|阈值|参数|处置)",
    re.IGNORECASE,
)
_NON_ABSTENTION_NEGATION = re.compile(r"未发现(?:明显)?异常", re.IGNORECASE)


def is_abstention_answer(answer: str | None) -> bool:
    """Detect a final semantic refusal so response metadata matches its text.

    This is deliberately narrow.  Phrases such as ``未发现异常`` must not be
    classified as abstention because they are factual conclusions, not a claim
    that the knowledge base lacks evidence.
    """

    normalized = " ".join(str(answer or "").split())
    # Markdown emphasis must not change the semantic classification.
    normalized = re.sub(r"[*_~`]", "", normalized)
    if not normalized:
        return False
    if any(pattern.search(normalized) for pattern in _ABSTENTION_PATTERNS):
        return True

    # Citation pruning can turn a paragraph-level refusal into a list where
    # every retained claim only states that the requested fact is absent.
    # Require at least two such claims and no positive claim to keep this rule
    # conservative.
    claim_lines = [
        re.sub(r"^\s*[-*+]\s*", "", line).strip()
        for line in str(answer or "").splitlines()
        if re.sub(r"^\s*[-*+]\s*", "", line).strip()
    ]
    absence_lines = [
        line
        for line in claim_lines
        if _ABSENCE_CLAIM.search(line) and not _NON_ABSTENTION_NEGATION.search(line)
    ]
    return len(absence_lines) >= 2 and len(absence_lines) == len(claim_lines)
