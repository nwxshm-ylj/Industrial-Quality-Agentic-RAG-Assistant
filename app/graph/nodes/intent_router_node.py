from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.graph.state import IndustrialRAGState


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


def intent_router_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    memory_text = _format_memory(state.get("memory_messages", []))

    system_prompt = """
你是一个工业RAG系统的意图识别器。

请根据用户问题，判断其属于以下哪一种意图：

1. doc_qa
普通工业文档问答，例如询问某个标准、SOP、设备说明、FMEA内容。

2. fault_diagnosis
故障诊断类问题，例如询问异常原因、排查步骤、处理建议、设备报警、AI视觉误判、OCR失败、扭矩报警。

3. case_search
历史案例查询，例如询问过去是否发生过类似问题、历史8D案例、相似故障、复发案例。

4. rule_query
规则查询，例如询问PR规则、配置映射、字段校验规则、判定规则。

5. sql_analysis
结构化数据分析，例如最近一周、统计、数量、趋势、Top问题、数据库记录、报警次数。

6. general
与工业知识库无关的一般问题。

要求：
结合历史对话理解当前问题中的指代和省略。
只输出一个标签，不要解释。
可选标签只能是：
doc_qa, fault_diagnosis, case_search, rule_query, sql_analysis, general
"""

    user_prompt = f"""
历史对话：
{memory_text}

用户当前问题：
{question}

请输出意图标签：
"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        intent = str(response.content).strip().lower()

        # 防止模型输出多余文本
        for valid_intent in VALID_INTENTS:
            if valid_intent in intent:
                intent = valid_intent
                break

        if intent not in VALID_INTENTS:
            intent = _rule_based_intent(question)

    except Exception as e:
        print("intent_router_node 调用失败:", repr(e))
        intent = _rule_based_intent(question)

    print("=" * 80)
    print("intent_router_node 完成")
    print("question:", question)
    print("intent:", intent)
    print("=" * 80)

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