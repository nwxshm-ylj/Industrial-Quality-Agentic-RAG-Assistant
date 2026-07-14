from app.prompting.models import PromptReference, RenderedPrompt


def get_prompt_registry():
    """延迟导入运行时 Factory，使离线 Prompt 校验不依赖模型配置。"""
    from app.prompting.factory import get_prompt_registry as _get_prompt_registry

    return _get_prompt_registry()

__all__ = [
    "PromptReference",
    "RenderedPrompt",
    "get_prompt_registry",
]
