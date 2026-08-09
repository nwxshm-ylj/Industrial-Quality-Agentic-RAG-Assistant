from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.configure_local_embedding import BGE_M3_ENV, update_env_file


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        env_file = Path(directory) / ".env"
        env_file.write_text(
            "LLM_API_KEY=keep-secret\n"
            "EMBEDDING_PROVIDER=qwen\n"
            "QDRANT_COLLECTION=industrial_docs_qwen_1024_v1\n",
            encoding="utf-8",
        )
        update_env_file(env_file, BGE_M3_ENV)
        first = env_file.read_text(encoding="utf-8")
        update_env_file(env_file, BGE_M3_ENV)
        second = env_file.read_text(encoding="utf-8")

    assert first == second, "env migration must be idempotent"
    assert "LLM_API_KEY=keep-secret" in first
    assert "EMBEDDING_PROVIDER=local" in first
    assert "QDRANT_COLLECTION=industrial_docs_bge_m3_1024_v1" in first
    assert "LOCAL_EMBEDDING_MODEL_PATH=/app/data/models/bge-m3" in first
    assert "industrial_memory_bge_m3_1024_v1" in first
    print("Local BGE-M3 env configuration tests passed")


if __name__ == "__main__":
    main()
