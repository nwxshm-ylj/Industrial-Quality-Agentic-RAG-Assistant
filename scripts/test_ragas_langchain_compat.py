from __future__ import annotations

import importlib

from app.evaluation.ragas_compat import install_ragas_langchain_compat


def main() -> None:
    installed = install_ragas_langchain_compat()
    legacy_module = importlib.import_module(
        "langchain_community.chat_models.vertexai"
    )
    assert isinstance(installed, bool)
    assert hasattr(legacy_module, "ChatVertexAI")

    # This is the import that failed before the compatibility layer ran.
    import ragas  # noqa: F401

    print("RAGAS LangChain compatibility test passed")


if __name__ == "__main__":
    main()
