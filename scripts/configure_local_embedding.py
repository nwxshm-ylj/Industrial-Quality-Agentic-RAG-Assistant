from __future__ import annotations

import argparse
from pathlib import Path


BGE_M3_ENV = {
    "QDRANT_COLLECTION": "industrial_docs_bge_m3_1024_v1",
    "EMBEDDING_PROVIDER": "local",
    "LOCAL_EMBEDDING_MODEL_NAME": "BAAI/bge-m3",
    "LOCAL_EMBEDDING_MODEL_PATH": "/app/data/models/bge-m3",
    "LOCAL_EMBEDDING_MODEL_REVISION": (
        "5617a9f61b028005a4858fdac845db406aefb181"
    ),
    "LOCAL_EMBEDDING_DIMENSION": "1024",
    "LOCAL_EMBEDDING_BATCH_SIZE": "8",
    "LOCAL_EMBEDDING_DEVICE": "cpu",
    "LOCAL_EMBEDDING_NORMALIZE_EMBEDDINGS": "true",
    "EMBEDDING_INDEX_VERSION": "bge-m3-1024-v1",
    "MEMORY_QDRANT_COLLECTION": "industrial_memory_bge_m3_1024_v1",
    "MEMORY_INDEX_VERSION": "bge-m3-v1",
}


def update_env_file(path: Path, values: dict[str, str]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Environment file does not exist: {path}")
    original = path.read_text(encoding="utf-8-sig")
    remaining = dict(values)
    output: list[str] = []
    for line in original.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    if remaining:
        output.extend(["", "# Local BGE-M3 text embedding"])
        output.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Switch an existing env file to the local BGE-M3 index."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--data-host-path",
        type=Path,
        help=(
            "Optional host data directory mounted at /app/data by Docker Compose. "
            "Useful when the env file and model data live in the main checkout."
        ),
    )
    args = parser.parse_args()
    values = dict(BGE_M3_ENV)
    if args.data_host_path is not None:
        resolved = args.data_host_path.expanduser().resolve()
        if not (resolved / "models" / "bge-m3").is_dir():
            raise FileNotFoundError(
                f"Pinned BGE-M3 model directory does not exist: "
                f"{resolved / 'models' / 'bge-m3'}"
            )
        values["DATA_HOST_PATH"] = resolved.as_posix()
    update_env_file(args.env_file, values)
    print(f"Configured local BGE-M3 embedding in: {args.env_file.resolve()}")


if __name__ == "__main__":
    main()
