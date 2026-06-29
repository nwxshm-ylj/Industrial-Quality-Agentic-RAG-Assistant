from app.rag.vectorstore import QdrantVectorStore


def main():
    vectorstore = QdrantVectorStore()

    questions = [
        "轮毂识别异常可能是什么原因？",
        "扭矩工位连续报警应该怎么排查？",
        "合格证OCR识别VIN失败怎么办？"
    ]

    for question in questions:
        print("=" * 80)
        print(f"问题: {question}")

        results = vectorstore.search(question, top_k=3)

        for i, result in enumerate(results, start=1):
            payload = result.payload

            print(f"\\nTop {i}")
            print(f"Score: {result.score}")
            print(f"Source: {payload.get('source')}")
            print(f"Doc Type: {payload.get('doc_type')}")
            print(f"Text: {payload.get('text')[:300]}")


if __name__ == "__main__":
    main()