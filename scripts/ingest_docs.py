from app.rag.loader import load_markdown_docs
from app.rag.splitter import split_docs
from app.rag.vectorstore import QdrantVectorStore
from app.rag.chunk_store import save_chunks


def main():
    raw_docs = load_markdown_docs("data/raw_docs")
    chunks = split_docs(raw_docs)

    print(f"读取文档数量: {len(raw_docs)}")
    print(f"切分 chunk 数量: {len(chunks)}")

    save_chunks(chunks)
    print("chunks 已保存到 data/processed/chunks.json")

    vectorstore = QdrantVectorStore()
    vectorstore.recreate_collection()
    vectorstore.add_chunks(chunks)

    print("文档已成功写入 Qdrant")


if __name__ == "__main__":
    main()