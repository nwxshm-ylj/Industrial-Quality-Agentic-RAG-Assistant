from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.graph.state import IndustrialRAGState


llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    temperature=0.1,
    max_tokens=512,
)


def query_rewriter_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    intent = state.get("intent", "doc_qa")
    retry_count = state.get("retry_count", 0)
    memory_text = _format_memory(state.get("memory_messages", []))

    system_prompt = """
你是一个工业RAG检索查询改写助手。

你的任务是把用户问题改写成更适合工业知识库检索的查询语句。

要求：
1. 保留用户原始意图。
2. 补充工业相关关键词。
3. 根据意图补充合适的检索方向。
4. 结合历史对话补全当前问题中的指代和省略，使查询可独立理解。
5. 不要回答问题。
6. 不要解释。
7. 只输出一行检索查询语句。
"""

    intent_hint = _get_intent_hint(intent)

    if retry_count == 0:
        user_prompt = f"""
历史对话：
{memory_text}

用户当前问题：
{question}

识别到的问题意图：
{intent}

意图说明：
{intent_hint}

请改写成适合工业知识库检索的查询语句。
"""
    else:
        user_prompt = f"""
历史对话：
{memory_text}

用户当前问题：
{question}

识别到的问题意图：
{intent}

上一次检索证据不足，请扩展更多同义词、工业术语和可能相关字段。
只输出一行新的检索查询语句。
"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        rewritten_query = str(response.content).strip()

        if not rewritten_query:
            rewritten_query = question

    except Exception as e:
        print("query_rewriter_node 调用失败:", repr(e))
        rewritten_query = question

    print("=" * 80)
    print("query_rewriter_node 完成")
    print("原始问题:", question)
    print("intent:", intent)
    print("改写查询:", rewritten_query)
    print("retry_count:", retry_count)
    print("=" * 80)

    return {
        "rewritten_query": rewritten_query
    }


def _format_memory(memory_messages: list[dict]) -> str:
    if not memory_messages:
        return "无历史对话。"

    return "\n".join(
        f"{message.get('role', 'unknown')}: {message.get('content', '')}"
        for message in memory_messages
    )


def _get_intent_hint(intent: str) -> str:
    hints = {
        "doc_qa": "优先检索设备手册、SOP、检验标准、FMEA等文档内容。",
        "fault_diagnosis": "优先检索故障现象、可能原因、排查步骤、处理措施、FMEA、8D案例。",
        "case_search": "优先检索历史质量案例、8D报告、相似故障、根因和措施。",
        "rule_query": "优先检索PR规则、配置映射、字段校验规则、判定标准。",
        "sql_analysis": "优先检索与结构化质量数据、报警记录、检测记录相关的字段说明。",
        "general": "普通问题，不需要扩展工业检索词。"
    }

    return hints.get(intent, hints["doc_qa"])