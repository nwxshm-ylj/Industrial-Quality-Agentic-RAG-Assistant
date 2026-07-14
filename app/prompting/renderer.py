from __future__ import annotations

from string import Formatter
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.prompting.exceptions import PromptConfigurationError, PromptRenderError
from app.prompting.models import PromptDefinition, PromptReference, RenderedPrompt


class StrictPromptRenderer:
    """使用受限的 Python format 语法渲染 Prompt，并严格校验输入变量。"""

    _ROLE_FACTORIES = {
        "system": SystemMessage,
        "user": HumanMessage,
        "assistant": AIMessage,
    }

    def render(
        self,
        definition: PromptDefinition,
        reference: PromptReference,
        variables: dict[str, Any],
    ) -> RenderedPrompt:
        declared = set(definition.variables)
        supplied = set(variables)
        undeclared = supplied - declared
        if undeclared:
            names = ", ".join(sorted(undeclared))
            raise PromptRenderError(f"Prompt 收到未声明变量: {names}")

        normalized: dict[str, str] = {}
        for name, spec in definition.variables.items():
            if name not in variables or variables[name] is None:
                if spec.required:
                    raise PromptRenderError(f"Prompt 缺少必要变量: {name}")
                normalized[name] = ""
                continue

            value = str(variables[name])
            if spec.max_length is not None and len(value) > spec.max_length:
                raise PromptRenderError(
                    f"Prompt 变量 {name} 超过最大长度 {spec.max_length}"
                )
            normalized[name] = value

        rendered_messages = []
        for message in definition.messages:
            factory = self._ROLE_FACTORIES.get(message.role)
            if factory is None:
                raise PromptConfigurationError(
                    f"不支持的 Prompt 消息角色: {message.role}"
                )
            self._validate_template_fields(message.template, declared)
            try:
                content = message.template.format_map(normalized)
            except (KeyError, ValueError) as exc:
                raise PromptRenderError(f"Prompt 渲染失败: {exc}") from exc
            rendered_messages.append(factory(content=content))

        return RenderedPrompt(
            messages=tuple(rendered_messages),
            reference=reference,
        )

    @staticmethod
    def _validate_template_fields(template: str, declared: set[str]) -> None:
        try:
            parsed = Formatter().parse(template)
            for _, field_name, format_spec, conversion in parsed:
                if field_name is None:
                    continue
                if "." in field_name or "[" in field_name:
                    raise PromptConfigurationError(
                        f"Prompt 禁止属性或下标访问: {field_name}"
                    )
                if format_spec or conversion:
                    raise PromptConfigurationError(
                        f"Prompt 禁止格式化转换: {field_name}"
                    )
                if field_name not in declared:
                    raise PromptConfigurationError(
                        f"模板引用了未声明变量: {field_name}"
                    )
        except ValueError as exc:
            raise PromptConfigurationError(f"Prompt 模板语法错误: {exc}") from exc
