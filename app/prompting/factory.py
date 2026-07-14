from functools import lru_cache

from app.core.config import settings
from app.core.logger import log_business_event
from app.prompting.registry import PromptRegistry


@lru_cache(maxsize=1)
def get_prompt_registry() -> PromptRegistry:
    try:
        registry = PromptRegistry(
            catalog_path=settings.prompt_catalog_path,
            release_path=settings.prompt_release_path,
        )
    except Exception as exc:
        log_business_event(
            "prompt_registry_load_failed",
            status="failed",
            error_message=str(exc),
            prompt_catalog_path=settings.prompt_catalog_path,
            prompt_release_path=settings.prompt_release_path,
        )
        raise

    metadata = registry.release_metadata()
    log_business_event(
        "prompt_registry_loaded",
        status="success",
        prompt_release=metadata["release_id"],
        prompt_channel=metadata["channel"],
        prompt_count=len(metadata["versions"]),
    )
    return registry


def clear_prompt_registry_cache() -> None:
    """仅用于测试或显式配置重载；生产请求链路不得调用。"""
    get_prompt_registry.cache_clear()
