from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_docs(raw_docs: list[dict]):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=["\\n## ", "\\n# ", "\\n", "。", ".", " "]
    )

    chunks = []

    for doc in raw_docs:
        texts = splitter.split_text(doc["content"])

        for i, text in enumerate(texts):
            chunks.append({
                "text": text,
                "metadata": {
                    "source": doc["source"],
                    "chunk_id": f"{doc['source']}_{i}",
                    "doc_type": infer_doc_type(doc["source"])
                }
            })

    return chunks


def infer_doc_type(filename: str) -> str:
    if "fmea" in filename.lower():
        return "FMEA"
    if "sop" in filename.lower():
        return "SOP"
    if "rule" in filename.lower():
        return "RULE"
    return "GENERAL"