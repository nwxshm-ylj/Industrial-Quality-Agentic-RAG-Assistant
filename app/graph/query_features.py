from __future__ import annotations

import re
from typing import Any

from app.traceability.entity_linker import QualityEntityLinker
from app.traceability.taxonomy import is_traceability_question


LEGACY_RAG_INTENTS = {
    "doc_qa",
    "fault_diagnosis",
    "case_search",
    "rule_query",
}

_DOCUMENT_SOURCE_TERMS = (
    "标准",
    "手册",
    "文档",
    "sop",
    "pfmea",
    "fmea",
    "lessonlearn",
    "lesson learned",
    "作业指导书",
    "工作指导书",
    "8d报告",
)

_SQL_ENTITY_TERMS = (
    "工位",
    "报警",
    "检验",
    "检测",
    "误识别",
    "不合格",
    "缺陷",
    "检验记录",
    "检测记录",
    "报警记录",
    "设备报警",
    "质量记录",
    "质量问题",
    "不合格记录",
    "缺陷记录",
    "数据库",
    "inspection_record",
    "equipment_alarm",
    "工位报警",
    "工位数据",
)

_SQL_OPERATION_TERMS = (
    "统计",
    "数量",
    "多少条",
    "多少次",
    "趋势",
    "占比",
    "平均",
    "总数",
    "最多",
    "最少",
    "top",
    "排名",
    "最近几条",
    "明细",
)

_GENERAL_EXACT = {
    "你好",
    "您好",
    "嗨",
    "hello",
    "hi",
    "谢谢",
    "感谢",
    "再见",
    "你是谁",
    "你能做什么",
    "怎么使用这个系统",
    "如何使用这个系统",
}

_INDUSTRIAL_TERMS = (
    "质量",
    "制造",
    "售后",
    "车辆",
    "车型",
    "零件",
    "工位",
    "设备",
    "故障",
    "异常",
    "报警",
    "扭矩",
    "焊缝",
    "轮毂",
    "标准",
    "案例",
    "风险",
    "检验",
    "检测",
    "pfmea",
    "lesson",
    "8d",
)

_PART_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]{8,18}(?![A-Za-z0-9]))"
    r"(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]+",
    re.IGNORECASE,
)
_CASE_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:LL[-_A-Za-z0-9]{3,}|8D[-_A-Za-z0-9]{2,})(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_INFERRED_FILTER_FIELDS = (
    "vehicle_models",
    "systems",
    "components",
    "processes",
    "stations",
    "failure_modes",
    "symptoms",
)


def normalize_intent_label(value: str | None) -> str:
    """Map historical labels to the three stable route intents."""
    normalized = str(value or "").strip().lower()
    if normalized in LEGACY_RAG_INTENTS:
        return "rag"
    if normalized == "sql_analysis":
        return "sql"
    if normalized in {"rag", "sql", "general"}:
        return normalized
    return "rag"


def is_sql_query(question: str) -> bool:
    """Conservatively identify queries answerable by the known SQL data domain."""
    normalized = str(question or "").strip().lower()
    if any(term in normalized for term in _DOCUMENT_SOURCE_TERMS):
        return False
    has_entity = any(term in normalized for term in _SQL_ENTITY_TERMS)
    has_operation = any(term in normalized for term in _SQL_OPERATION_TERMS)
    return has_entity and has_operation


def is_general_chat(question: str) -> bool:
    normalized = str(question or "").strip().lower().rstrip("！!。?.？")
    return normalized in _GENERAL_EXACT


def has_industrial_signal(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    return any(term in normalized for term in _INDUSTRIAL_TERMS)


def classify_task_mode(question: str) -> str:
    """Classify a RAG query without changing the stable top-level route."""
    normalized = str(question or "").strip().lower()
    if any(
        term in normalized
        for term in ("根因", "原因", "为什么", "为何", "因果", "原因追溯")
    ):
        return "cause_trace"
    if any(
        term in normalized
        for term in (
            "案例",
            "类似问题",
            "历史问题",
            "经验教训",
            "lessonlearn",
            "lesson learned",
            "有哪些缺陷",
            "缺陷有哪些",
            "有哪些问题",
            "问题有哪些",
            "售后缺陷",
            "售后问题",
            "客户抱怨",
        )
    ) or (
        "售后" in normalized
        and any(term in normalized for term in ("哪些", "问题", "缺陷", "抱怨"))
    ):
        return "case_search"
    if any(
        term in normalized
        for term in (
            "怎么做",
            "如何做",
            "怎么处理",
            "如何处理",
            "如何检查",
            "排查步骤",
            "检查步骤",
            "返工方法",
            "返工",
            "返修",
            "修复方法",
            "修复",
            "操作步骤",
        )
    ):
        return "procedure_lookup"
    return "knowledge_lookup"


def _extract_case_anchors(
    question: str,
    entities: dict[str, list[dict[str, str]]],
) -> list[str]:
    anchors = [
        item["name"]
        for item in entities.get("vehicle_models", [])
        if item.get("name")
    ]
    anchors.extend(_PART_NUMBER_PATTERN.findall(question or ""))
    anchors.extend(_CASE_ID_PATTERN.findall(question or ""))
    return list(dict.fromkeys(str(value).strip() for value in anchors if value))


def extract_query_features(question: str, intent: str) -> dict[str, Any]:
    normalized = str(question or "").strip().lower()
    task_mode = classify_task_mode(question)
    traceability_required = is_traceability_question(question) or task_mode in {
        "case_search",
        "cause_trace",
    }
    diagnosis_required = any(
        term in normalized
        for term in (
            "原因",
            "根因",
            "排查",
            "故障",
            "异常",
            "失效",
            "报警",
            "怎么处理",
            "如何处理",
        )
    )

    requested_aspects: list[str] = []
    aspect_terms = {
        "root_cause": ("原因", "根因", "为什么", "为何"),
        "diagnostic_steps": ("排查", "检查步骤", "优先检查", "先查"),
        "corrective_action": ("措施", "整改", "改进", "处理", "对策"),
        "risk": ("风险", "影响", "后果", "失效"),
        "similar_cases": ("案例", "类似", "历史", "复发", "lesson"),
        "standard_requirement": (
            "标准",
            "要求",
            "规范",
            "规定",
            "规则",
            "配置",
            "映射",
            "判定",
            "sop",
        ),
    }
    for aspect, terms in aspect_terms.items():
        if any(term in normalized for term in terms):
            requested_aspects.append(aspect)

    preferred_doc_types: list[str] = []
    type_terms = {
        "LESSON_LEARNED": ("lessonlearn", "lesson learned", "经验教训"),
        "STANDARD_WORK_DOCUMENT": (
            "标准",
            "规范",
            "规则",
            "配置",
            "映射",
            "判定",
            "sop",
            "作业指导书",
            "工作指导书",
        ),
        "PFMEA": ("pfmea", "p-fmea", "fmea", "失效模式"),
        "AFTERSALES_DOCUMENT": ("售后", "客户抱怨", "质保", "8d"),
    }
    for doc_type, terms in type_terms.items():
        if any(term in normalized for term in terms):
            preferred_doc_types.append(doc_type)
    if traceability_required:
        for doc_type in (
            "LESSON_LEARNED",
            "STANDARD_WORK_DOCUMENT",
            "PFMEA",
            "AFTERSALES_DOCUMENT",
        ):
            if doc_type not in preferred_doc_types:
                preferred_doc_types.append(doc_type)

    linked_entities = QualityEntityLinker().link(question)
    flat_entities = QualityEntityLinker.flatten(linked_entities)
    case_anchors = _extract_case_anchors(question, linked_entities)
    inferred_filters = {
        field: flat_entities[field]
        for field in _INFERRED_FILTER_FIELDS
        if flat_entities.get(field)
    }

    return {
        "task_mode": task_mode,
        "traceability_required": traceability_required,
        "diagnosis_required": diagnosis_required,
        "structured_data_required": intent == "sql",
        "requested_aspects": requested_aspects,
        "preferred_doc_types": preferred_doc_types,
        "entities": linked_entities,
        "case_anchors": case_anchors,
        "requires_case_anchor": task_mode == "cause_trace" and not case_anchors,
        "inferred_filters": inferred_filters,
    }
