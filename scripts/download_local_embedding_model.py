from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MODEL_ID = "BAAI/bge-m3"
DEFAULT_MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DEFAULT_DESTINATION = Path("data/models/bge-m3")
REQUIRED_FILES = (
    "1_Pooling/config.json",
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "pytorch_model.bin",
    "sentence_bert_config.json",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
)
DOWNLOAD_PATTERNS = (*REQUIRED_FILES, "README.md")


def download_model(
    *,
    model_id: str,
    revision: str,
    destination: Path,
) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is unavailable; run this script in the API image"
        ) from exc

    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=model_id,
        revision=revision,
        local_dir=str(destination),
        allow_patterns=list(DOWNLOAD_PATTERNS),
    )
    missing = [
        relative_path
        for relative_path in REQUIRED_FILES
        if not (destination / relative_path).is_file()
    ]
    if missing:
        raise RuntimeError(
            "Local BGE-M3 snapshot is incomplete: " + ", ".join(missing)
        )
    provenance = {
        "model_id": model_id,
        "revision": revision,
        "embedding_dimension": 1024,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "source": f"https://huggingface.co/{model_id}",
    }
    (destination / "MODEL_PROVENANCE.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the pinned BAAI/bge-m3 snapshot for offline use."
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_DESTINATION,
    )
    args = parser.parse_args()
    destination = download_model(
        model_id=args.model_id,
        revision=args.revision,
        destination=args.destination,
    )
    print(f"Local embedding model ready: {destination}")


if __name__ == "__main__":
    main()
