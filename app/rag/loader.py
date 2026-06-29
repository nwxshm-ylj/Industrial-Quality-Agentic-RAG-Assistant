from pathlib import Path


def load_markdown_docs(folder: str):
    docs = []

    for path in Path(folder).glob("*.md"):
        text = path.read_text(encoding="utf-8")

        docs.append({
            "source": path.name,
            "content": text
        })

    return docs