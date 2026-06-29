import json
from pathlib import Path


DEFAULT_CHUNK_PATH = "data/processed/chunks.json"


def save_chunks(chunks: list[dict], path: str = DEFAULT_CHUNK_PATH) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def load_chunks(path: str = DEFAULT_CHUNK_PATH) -> list[dict]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"未找到 chunks 文件: {file_path}. 请先运行 python -m scripts.ingest_docs"
        )

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)