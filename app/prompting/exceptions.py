class PromptError(RuntimeError):
    """Prompt 子系统基础异常。"""


class PromptConfigurationError(PromptError):
    """Prompt Catalog 或 Release Manifest 配置不合法。"""


class PromptNotFoundError(PromptError):
    """活动 Release 中不存在指定 Prompt 组件。"""


class PromptRenderError(PromptError):
    """Prompt 输入变量不符合声明或无法安全渲染。"""
