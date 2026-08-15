from __future__ import annotations

from pathlib import Path


UPLOAD_DOCUMENT_TYPES = {
    "LESSON_LEARNED",
    "STANDARD_WORK_DOCUMENT",
    "PFMEA",
    "AFTERSALES_DOCUMENT",
}

DOCUMENT_TYPES = {
    *UPLOAD_DOCUMENT_TYPES,
    "STANDARD",
    "WORK_INSTRUCTION",
    "AFTERSALES_CASE",
    "EIGHT_D_REPORT",
    "GENERAL",
}

_DOCUMENT_TYPE_ALIASES = {
    "8D": "AFTERSALES_DOCUMENT",
    "8D_REPORT": "AFTERSALES_DOCUMENT",
    "EIGHT_D_REPORT": "AFTERSALES_DOCUMENT",
    "AFTER_SALES_CASE": "AFTERSALES_DOCUMENT",
    "AFTERSALES_CASE": "AFTERSALES_DOCUMENT",
    "CASE": "AFTERSALES_DOCUMENT",
    "FMEA": "PFMEA",
    "LL": "LESSON_LEARNED",
    "LESSONLEARNED": "LESSON_LEARNED",
    "LESSON_LEARNT": "LESSON_LEARNED",
    "STANDARD": "STANDARD_WORK_DOCUMENT",
    "QUALITY_STANDARD": "STANDARD_WORK_DOCUMENT",
    "RULE": "STANDARD_WORK_DOCUMENT",
    "SOP": "STANDARD_WORK_DOCUMENT",
    "WORK_GUIDE": "STANDARD_WORK_DOCUMENT",
    "WORK_INSTRUCTION": "STANDARD_WORK_DOCUMENT",
    "LESSONLEARN": "LESSON_LEARNED",
    "LESSON_LEARN": "LESSON_LEARNED",
    "标准作业文档": "STANDARD_WORK_DOCUMENT",
    "售后文档": "AFTERSALES_DOCUMENT",
}

DOCUMENT_TYPE_LABELS = {
    "LESSON_LEARNED": "LessonLearn",
    "STANDARD_WORK_DOCUMENT": "标准作业文档",
    "PFMEA": "PFMEA",
    "AFTERSALES_DOCUMENT": "售后文档",
}


def normalize_document_type(value: str | None, *, filename: str = "") -> str:
    """Return the canonical type used by the single logical knowledge base."""

    normalized = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    normalized = _DOCUMENT_TYPE_ALIASES.get(normalized, normalized)
    if normalized in DOCUMENT_TYPES:
        return normalized
    return infer_document_type(filename) if filename else "GENERAL"


def normalize_upload_document_type(value: str | None) -> str:
    """Validate an explicit category selected during managed document upload."""

    raw_value = (value or "").strip()
    if not raw_value:
        raise ValueError("上传文档时必须选择文档标签")
    normalized = normalize_document_type(raw_value)
    if normalized not in UPLOAD_DOCUMENT_TYPES:
        labels = "、".join(DOCUMENT_TYPE_LABELS.values())
        raise ValueError(f"不支持的文档标签: {raw_value}。可选标签: {labels}")
    return normalized


def infer_document_type(filename: str) -> str:
    name = Path(filename).name.lower()
    if name.startswith("ll-") or "lessonlearn" in name or "lesson_learn" in name:
        return "LESSON_LEARNED"
    if "8d" in name:
        return "AFTERSALES_DOCUMENT"
    if "pfmea" in name or "p-fmea" in name or "fmea" in name:
        return "PFMEA"
    if any(
        token in name
        for token in ("工作指导书", "作业指导书", "sop", "work_instruction")
    ):
        return "STANDARD_WORK_DOCUMENT"
    if any(
        token in name
        for token in ("标准化", "标准", "规范", "standard", "specification", "rule")
    ):
        return "STANDARD_WORK_DOCUMENT"
    if any(
        token in name
        for token in ("售后", "客户抱怨", "质保", "warranty", "aftersales")
    ):
        return "AFTERSALES_DOCUMENT"
    return "GENERAL"


TRACEABILITY_ROLE_BY_DOCUMENT_TYPE = {
    "STANDARD_WORK_DOCUMENT": "manufacturing_standard",
    "AFTERSALES_DOCUMENT": "field_evidence",
    "STANDARD": "manufacturing_standard",
    "WORK_INSTRUCTION": "process_instruction",
    "PFMEA": "process_risk",
    "AFTERSALES_CASE": "field_evidence",
    "EIGHT_D_REPORT": "root_cause_and_action",
    "LESSON_LEARNED": "lesson_learned",
    "GENERAL": "supporting_evidence",
}


def traceability_role(doc_type: str | None) -> str:
    return TRACEABILITY_ROLE_BY_DOCUMENT_TYPE.get(
        normalize_document_type(doc_type),
        "supporting_evidence",
    )


def is_traceability_question(question: str) -> bool:
    q = (question or "").lower()
    direct_match = any(
        keyword in q
        for keyword in (
            "lessonlearn",
            "lesson learned",
            "经验教训",
            "8d",
            "追溯",
            "售后风险",
            "风险传递",
            "风险扩散",
            "相似案例",
            "类似案例",
            "历史案例",
            "案例追溯",
            "类似问题",
            "复发案例",
        )
    )
    cross_stage_match = (
        "售后" in q
        and any(
            keyword in q
            for keyword in ("制造", "标准", "风险", "类似", "8d", "lesson")
        )
    )
    return direct_match or cross_stage_match
