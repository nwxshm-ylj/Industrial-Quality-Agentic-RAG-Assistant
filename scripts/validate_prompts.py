from __future__ import annotations

import json
from pathlib import Path

from app.prompting.registry import PromptRegistry


CATALOG_PATH = Path("prompts/catalog")
RELEASE_PATHS = (
    Path("prompts/releases/stable.yaml"),
    Path("prompts/releases/candidate.yaml"),
)


def main() -> None:
    validated = []
    for release_path in RELEASE_PATHS:
        registry = PromptRegistry(
            catalog_path=CATALOG_PATH,
            release_path=release_path,
        )
        metadata = registry.release_metadata()
        assert len(metadata["versions"]) == 5
        validated.append(metadata)

    print("Prompt Release 校验通过：")
    print(json.dumps(validated, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
