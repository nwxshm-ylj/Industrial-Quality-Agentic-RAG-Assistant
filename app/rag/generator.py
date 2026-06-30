from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings


class AnswerGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.1,
            max_tokens=1024,
        )

    def generate(
        self,
        question: str,
        contexts: list[dict],
        memory_messages: list[dict] | None = None,
    ) -> str:
        context_text = self._format_contexts(contexts)
        memory_text = self._format_memory(memory_messages)

        system_prompt = """
你是一个工业质量知识库助手，擅长根据设备手册、FMEA、SOP、质量案例和规则文档回答制造现场问题。

回答要求：
1. 必须以给定的参考资料作为事实依据。
2. 历史对话只用于理解上下文和指代，不能替代参考资料。
3. 如果资料中没有依据，不要编造。
4. 回答要结构化。
5. 对故障诊断类问题，按照“可能原因、排查步骤、处理建议、依据来源”组织。
6. 不要输出无依据的绝对结论。
"""

        user_prompt = f"""
历史对话：
{memory_text}

用户当前问题：
{question}

参考资料：
{context_text}

请结合历史对话和参考资料回答用户当前问题，并以参考资料作为主要依据。
"""

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        content = response.content


        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )

        if not content:
            return "模型已调用，但返回内容为空。请检查 generator.py 或模型返回结构。"

        return str(content)

    def _format_memory(
        self,
        memory_messages: list[dict] | None,
    ) -> str:
        if not memory_messages:
            return "无历史对话。"

        role_names = {
            "user": "用户",
            "assistant": "助手",
        }
        return "\n".join(
            f"{role_names.get(message.get('role'), message.get('role', '未知'))}："
            f"{message.get('content', '')}"
            for message in memory_messages
        )

    def _format_contexts(self, contexts: list[dict]) -> str:
        if not contexts:
            return "未检索到相关资料。"

        formatted = []

        for i, ctx in enumerate(contexts, start=1):
            formatted.append(
                f"""【资料{i}】
来源：{ctx.get("source")}
类型：{ctx.get("doc_type")}
chunk_id：{ctx.get("chunk_id")}
内容：
{ctx.get("text")}
"""
            )

        return "\n".join(formatted)