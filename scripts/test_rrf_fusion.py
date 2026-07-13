from app.rag.fusion import reciprocal_rank_fusion


def main() -> None:
    vector_results = [
        {"chunk_id": "c1", "text": "A", "score": 0.91},
        {"chunk_id": "c2", "text": "B", "score": 0.82},
    ]
    keyword_results = [
        {"chunk_id": "c2", "text": "B", "score": 8.0},
        {"chunk_id": "c3", "text": "C", "score": 5.0},
    ]

    results = reciprocal_rank_fusion(
        vector_results,
        keyword_results,
        rrf_k=60,
    )

    assert [item["chunk_id"] for item in results] == ["c2", "c1", "c3"]
    shared = results[0]
    assert shared["retrieval_source"] == "keyword+vector"
    assert shared["vector_score"] == 0.82
    assert shared["keyword_score"] == 8.0
    assert shared["bm25_score"] == 8.0
    assert shared["hybrid_score"] == shared["rrf_score"]
    assert shared["evidence_signal_score"] == 0.82
    assert shared["final_score_type"] == "rrf_score"
    print("RRF fusion tests passed")


if __name__ == "__main__":
    main()
