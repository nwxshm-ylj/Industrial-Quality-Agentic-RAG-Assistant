from app.rag.hybrid_retriever import HybridRetriever


def main():
    retriever = HybridRetriever()

    questions = [
        "ZP8 工位轮毂误识别可能是什么原因？",
        "OCR VIN 字段识别失败怎么办？",
        "扭矩工位连续报警应该怎么排查？",
    ]

    for question in questions:
        print("=" * 100)
        print("question:", question)

        results = retriever.retrieve(
            question=question,
            top_k=5,
            vector_top_k=20,
            bm25_top_k=20,
            rerank_candidate_k=20,
        )

        for idx, item in enumerate(results, start=1):
            print("-" * 80)
            print("rank:", idx)
            print("source:", item.get("source"))
            print("doc_type:", item.get("doc_type"))
            print("chunk_id:", item.get("chunk_id"))
            print("retrieval_source:", item.get("retrieval_source"))
            print("vector_score:", item.get("vector_score"))
            print("bm25_score:", item.get("bm25_score"))
            print("hybrid_score:", item.get("hybrid_score"))
            print("rerank_score:", item.get("rerank_score"))
            print("final_score_type:", item.get("final_score_type"))
            print("text:", item.get("text", "")[:300])


if __name__ == "__main__":
    main()