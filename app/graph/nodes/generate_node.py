from __future__ import annotations

from app.core.config import settings
from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.rag.generator import AnswerGenerator
from app.streaming.events import emit_answer_token


generator = AnswerGenerator()


def _trusted_tool_evidence(state: IndustrialRAGState) -> bool:
    if state.get("rule_result"):
        return True
    sql_result = state.get("sql_result")
    return bool(sql_result and not sql_result.get("error"))


def _refusal_answer(state: IndustrialRAGState) -> str:
    reason = state.get("abstain_reason") or "当前知识库证据不足"
    missing = state.get("missing_aspects", [])
    missing_text = f"，缺少：{'、'.join(missing)}" if missing else ""
    return (
        f"根据当前检索到的资料，暂时无法可靠回答该问题。{reason}{missing_text}。"
        "请补充更具体的车型、部件、工位、故障现象或相关文档后再试。"
    )


@observe_node("generate")
def generate_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    contexts = state.get("generation_contexts") or state.get("contexts", [])
    intent = state.get("intent", "rag")
    memory_messages = state.get("memory_messages", [])

    if intent == "general" and not contexts:
        answer = (
            "当前系统主要面向工业质量知识问答、故障诊断、质量数据分析和问题追溯。"
            "请提供具体的车型、部件、工位、故障现象或质量问题。"
        )
        answer_abstained = False
        emit_answer_token(answer)
    elif (state.get("sql_result") or {}).get("error"):
        answer = "结构化数据查询执行失败，当前无法给出可靠的数据结论，请稍后重试。"
        answer_abstained = True
        emit_answer_token(answer)
    elif (
        settings.generation_refusal_enabled
        and not _trusted_tool_evidence(state)
        and not state.get("evidence_enough", False)
    ):
        answer = _refusal_answer(state)
        answer_abstained = True
        emit_answer_token(answer)
    else:
        answer = generator.generate(
            question=question,
            contexts=contexts,
            memory_messages=memory_messages,
            intent=intent,
            evidence_enough=(
                state.get("evidence_enough", False) or _trusted_tool_evidence(state)
            ),
            evidence_confidence=state.get("evidence_confidence", 0.0),
            missing_aspects=state.get("missing_aspects", []),
        )
        answer_abstained = False

    return {
        "draft_answer": answer,
        "answer": answer,
        "answer_abstained": answer_abstained,
        "generation_retry_count": 0,
    }
