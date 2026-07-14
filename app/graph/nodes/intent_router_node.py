from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logger import log_business_event, observe_node
from app.graph.state import IndustrialRAGState
from app.observability.model_usage import invoke_observed_chat_model
from app.prompting import get_prompt_registry


llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    temperature=0,
    max_tokens=256,
)


VALID_INTENTS = {
    "doc_qa",
    "fault_diagnosis",
    "case_search",
    "rule_query",
    "sql_analysis",
    "general",
}


@observe_node("intent_router")
def intent_router_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    memory_text = _format_memory(state.get("memory_messages", []))

    try:
        rendered_prompt = get_prompt_registry().render(
            "intent_router",
            {
                "memory_text": memory_text,
                "question": question,
            },
        )
        response = invoke_observed_chat_model(
            llm,
            list(rendered_prompt.messages),
            component="intent_router",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_reference=rendered_prompt.reference,
        )

        intent = str(response.content).strip().lower()

        # 防止模型输出多余文本
        for valid_intent in VALID_INTENTS:
            if valid_intent in intent:
                intent = valid_intent
                break

        if intent not in VALID_INTENTS:
            intent = _rule_based_intent(question)

    except Exception as exc:
        log_business_event(
            "intent_router_model_fallback",
            request_id=state.get("request_id"),
            session_id=state.get("session_id"),
            status="failed",
            error_message=type(exc).__name__,
            prompt_component="intent_router",
        )
        intent = _rule_based_intent(question)

    return {
        "intent": intent
    }


def _format_memory(memory_messages: list[dict]) -> str:
    if not memory_messages:
        return "无历史对话。"

    return "\n".join(
        f"{message.get('role', 'unknown')}: {message.get('content', '')}"
        for message in memory_messages
    )


def _rule_based_intent(question: str) -> str:
    """
    LLM 失败或输出异常时的规则兜底。
    注意判断顺序：
    case_search 要放在 fault_diagnosis 前面，
    因为“历史轮毂误识别案例”同时包含“误识别”和“案例”。
    """
    q = question.lower()

    sql_keywords = [
        "最近",
        "统计",
        "数量",
        "趋势",
        "top",
        "top10",
        "多少",
        "占比",
        "数据库",
        "记录",
        "一周",
        "一个月",
        "30天",
        "7天",
        "最多",
        "最低",
        "最高",
        "平均",
    ]

    case_keywords = [
        "历史",
        "案例",
        "类似",
        "8d",
        "复发",
        "曾经",
        "之前",
        "以前",
        "发生过",
    ]

    rule_keywords = [
        "规则",
        "pr",
        "配置",
        "映射",
        "校验",
        "判定",
        "字段",
        "对应",
    ]

    fault_keywords = [
        "异常",
        "故障",
        "报警",
        "原因",
        "排查",
        "处理",
        "误识别",
        "识别失败",
        "失败",
        "不一致",
        "漏检",
        "误报",
    ]

    if any(k in q for k in sql_keywords):
        return "sql_analysis"

    if any(k in q for k in case_keywords):
        return "case_search"

    if any(k in q for k in rule_keywords):
        return "rule_query"

    if any(k in q for k in fault_keywords):
        return "fault_diagnosis"

    return "doc_qa"


def route_after_intent(state: IndustrialRAGState) -> str:
    """
    根据 intent 决定后续路径。
    """
    intent = state.get("intent", "doc_qa")

    if intent == "general":
        return "generate"

    if intent == "rule_query":
        return "rule"

    if intent == "sql_analysis":
        return "sql"

    if intent == "case_search":
        return "case"

    return "rag"
