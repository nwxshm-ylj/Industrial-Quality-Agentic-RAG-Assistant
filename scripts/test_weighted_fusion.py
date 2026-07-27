from app.rag.fusion import weighted_score_fusion


def main() -> None:
    vector_results = [
        {"chunk_id": "c1", "text": "A", "score": 0.95},
        {"chunk_id": "c2", "text": "B", "score": 0.70},
    ]
    keyword_results = [
        {"chunk_id": "c2", "text": "B", "score": 12.0},
        {"chunk_id": "c3", "text": "C", "score": 3.0},
    ]

    results = weighted_score_fusion(
        vector_results,
        keyword_results,
        vector_weight=0.65,
        keyword_weight=0.35,
    )

    assert [item["chunk_id"] for item in results] == ["c1", "c2", "c3"]
    assert results[0]["weighted_score"] == 0.65
    assert results[1]["weighted_score"] == 0.35
    assert results[1]["retrieval_source"] == "keyword+vector"
    assert results[1]["vector_score"] == 0.70
    assert results[1]["keyword_score"] == 12.0
    assert results[1]["final_score_type"] == "weighted_score"

    try:
        weighted_score_fusion([], [], vector_weight=0.0, keyword_weight=0.0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero fusion weights must be rejected")

    print("Weighted score fusion tests passed")


if __name__ == "__main__":
    main()
