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
    temperature=0.1,
    max_tokens=512,
)


@observe_node("query_rewriter")
def query_rewriter_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    intent = state.get("intent", "doc_qa")
    retry_count = state.get("retry_count", 0)
    memory_text = _format_memory(state.get("memory_messages", []))

    intent_hint = _get_intent_hint(intent)

    try:
        if retry_count == 0:
            prompt_component = "query_rewriter_initial"
            prompt_variables = {
                "memory_text": memory_text,
                "question": question,
                "intent": intent,
                "intent_hint": intent_hint,
            }
        else:
            prompt_component = "query_rewriter_retry"
            prompt_variables = {
                "memory_text": memory_text,
                "question": question,
                "intent": intent,
            }

        rendered_prompt = get_prompt_registry().render(
            prompt_component,
            prompt_variables,
        )
        response = invoke_observed_chat_model(
            llm,
            list(rendered_prompt.messages),
            component="query_rewriter",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_reference=rendered_prompt.reference,
        )

        rewritten_query = str(response.content).strip()

        if not rewritten_query:
            rewritten_query = question

    except Exception as exc:
        log_business_event(
            "query_rewriter_model_fallback",
            request_id=state.get("request_id"),
            session_id=state.get("session_id"),
            status="failed",
            error_message=type(exc).__name__,
            prompt_component=(
                "query_rewriter_initial"
                if retry_count == 0
                else "query_rewriter_retry"
            ),
        )
        rewritten_query = question

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
