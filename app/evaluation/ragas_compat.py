"""Narrow compatibility helpers for optional RAGAS integrations."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

from app.core.logger import log_business_event


_LEGACY_VERTEX_MODULE = "langchain_community.chat_models.vertexai"


def install_ragas_langchain_compat() -> bool:
    """Provide the legacy ChatVertexAI symbol expected by RAGAS 0.4.3.

    Modern ``langchain-community`` versions removed this module after moving
    the integration to a standalone package. RAGAS imports the class eagerly
    even when an evaluation uses a non-Vertex provider. The local evaluator
    uses Qwen through an OpenAI-compatible client, so a non-instantiable type
    is sufficient for RAGAS' provider type registry.

    Returns ``True`` only when the compatibility module was installed.
    """

    try:
        importlib.import_module(_LEGACY_VERTEX_MODULE)
        return False
    except ModuleNotFoundError as exc:
        if exc.name != _LEGACY_VERTEX_MODULE:
            raise

    module = ModuleType(_LEGACY_VERTEX_MODULE)

    class ChatVertexAI:  # pragma: no cover - must never be instantiated here
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "VertexAI is not configured for this project. Install and use "
                "langchain-google-vertexai directly if that provider is needed."
            )

    ChatVertexAI.__module__ = _LEGACY_VERTEX_MODULE
    module.ChatVertexAI = ChatVertexAI
    sys.modules[_LEGACY_VERTEX_MODULE] = module
    log_business_event(
        "ragas_langchain_compat_installed",
        status="success",
        compatibility_module=_LEGACY_VERTEX_MODULE,
    )
    return True
