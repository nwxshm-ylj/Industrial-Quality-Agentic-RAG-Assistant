from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState


_TRUNCATION_MARKER = "\n[内容因上下文预算截断]"
_OMISSION_MARKER = "\n[...省略非关键内容...]\n"
_SEMANTIC_BOUNDARY = re.compile(r"(?<=[。！？；.!?;])|[\r\n]+")
_HIGH_PRIORITY_MARKERS = (
    "结论",
    "根因",
    "原因",
    "风险",
    "后果",
    "要求",
    "必须",
    "禁止",
    "不得",
    "注意",
    "警告",
    "措施",
    "对策",
    "判定",
    "标准",
)
_ACTION_MARKERS = (
    "检查",
    "调整",
    "更换",
    "校准",
    "停机",
    "返工",
    "隔离",
    "验证",
    "放行",
)


def _context_key(context: dict[str, Any]) -> str:
    chunk_id = str(context.get("chunk_id") or "").strip()
    if chunk_id:
        return f"chunk:{chunk_id}"
    return "text:" + " ".join(str(context.get("text") or "").split())


def _semantic_units(text: str) -> list[str]:
    return [unit.strip() for unit in _SEMANTIC_BOUNDARY.split(text) if unit.strip()]


def _priority_score(unit: str) -> int:
    score = 0
    if unit.startswith(("[章节]", "[页码]", "#")):
        score += 8
    score += 6 * sum(marker in unit for marker in _HIGH_PRIORITY_MARKERS)
    score += 3 * sum(marker in unit for marker in _ACTION_MARKERS)
    if re.search(r"\d+(?:\.\d+)?\s*(?:%|mm|cm|m|N(?:m)?|V|A|℃|°C|MPa|kPa)?", unit):
        score += 4
    return score


def _render_units(units: list[str], selected_indexes: set[int]) -> str:
    pieces: list[str] = []
    previous_index: int | None = None
    for index in sorted(selected_indexes):
        if previous_index is not None:
            pieces.append("\n" if index == previous_index + 1 else _OMISSION_MARKER)
        pieces.append(units[index])
        previous_index = index
    return "".join(pieces)


def _truncate_context_text(text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
    """Fit text to a character budget while retaining high-value evidence."""
    if len(text) <= max_chars:
        return text, {
            "truncated": False,
            "priority_fragments_preserved": 0,
            "strategy": "full_text",
        }
    if max_chars <= len(_TRUNCATION_MARKER):
        return text[:max_chars], {
            "truncated": True,
            "priority_fragments_preserved": 0,
            "strategy": "hard_limit",
        }

    content_budget = max_chars - len(_TRUNCATION_MARKER)
    units = _semantic_units(text)
    if not units:
        return text[:content_budget].rstrip() + _TRUNCATION_MARKER, {
            "truncated": True,
            "priority_fragments_preserved": 0,
            "strategy": "head_fallback",
        }

    scores = [_priority_score(unit) for unit in units]
    priority_indexes = sorted(
        (index for index, score in enumerate(scores) if score > 0),
        key=lambda index: (-scores[index], index),
    )
    if priority_indexes and len(units[priority_indexes[0]]) > content_budget:
        selected_text = units[priority_indexes[0]][:content_budget].rstrip()
        return selected_text + _TRUNCATION_MARKER, {
            "truncated": True,
            "priority_fragments_preserved": 1,
            "strategy": "priority_fragment_excerpt",
        }
    candidate_indexes = list(
        dict.fromkeys(priority_indexes + [0, len(units) - 1] + list(range(len(units))))
    )
    selected_indexes: set[int] = set()
    for index in candidate_indexes:
        candidate = _render_units(units, selected_indexes | {index})
        if len(candidate) <= content_budget:
            selected_indexes.add(index)

    if not selected_indexes:
        best_index = priority_indexes[0] if priority_indexes else 0
        selected_text = units[best_index][:content_budget].rstrip()
    else:
        selected_text = _render_units(units, selected_indexes).rstrip()

    return selected_text + _TRUNCATION_MARKER, {
        "truncated": True,
        "priority_fragments_preserved": sum(
            1 for index in selected_indexes if scores[index] > 0
        ),
        "strategy": "priority_fragments",
    }


def build_generation_contexts(
    contexts: list[dict[str, Any]], *, max_items: int, max_chars: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deduplicate and budget evidence without changing retrieval citations."""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    consumed_chars = 0
    truncated = False
    duplicate_count = 0
    truncated_context_count = 0
    priority_fragments_preserved = 0

    for context in contexts:
        text = str(context.get("text") or "").strip()
        if not text:
            continue
        key = _context_key(context)
        if key in seen:
            duplicate_count += 1
            continue
        if len(selected) >= max_items or consumed_chars >= max_chars:
            truncated = True
            break
        seen.add(key)
        remaining = max_chars - consumed_chars
        selected_text, truncation_info = _truncate_context_text(text, remaining)
        if truncation_info["truncated"]:
            truncated = True
            truncated_context_count += 1
            priority_fragments_preserved += int(
                truncation_info["priority_fragments_preserved"]
            )
        selected.append(
            {
                **context,
                "text": selected_text,
                "evidence_id": f"E{len(selected) + 1}",
                "citation_label": f"资料{len(selected) + 1}",
            }
        )
        consumed_chars += len(selected_text)

    metadata = {
        "input_context_count": len(contexts),
        "generation_context_count": len(selected),
        "generation_context_chars": consumed_chars,
        "deduplicated_count": duplicate_count,
        "truncated": truncated,
        "truncated_context_count": truncated_context_count,
        "priority_fragments_preserved": priority_fragments_preserved,
        "truncation_strategy": "priority_fragments",
        "max_items": max_items,
        "max_chars": max_chars,
    }
    return selected, metadata


@observe_node("context_builder")
def context_builder_node(state: IndustrialRAGState) -> dict:
    contexts, metadata = build_generation_contexts(
        state.get("contexts", []),
        max_items=settings.generation_context_max_items,
        max_chars=settings.generation_context_max_chars,
    )
    return {"generation_contexts": contexts, "generation_context_metadata": metadata}
