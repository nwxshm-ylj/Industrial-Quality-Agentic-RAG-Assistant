from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.observability.model_usage import invoke_observed_chat_model
from app.prompting import get_prompt_registry


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

        rendered_prompt = get_prompt_registry().render(
            "answer_generator",
            {
                "memory_text": memory_text,
                "question": question,
                "context_text": context_text,
            },
        )

        response = invoke_observed_chat_model(
            self.llm,
            list(rendered_prompt.messages),
            component="answer_generator",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_reference=rendered_prompt.reference,
        )

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
