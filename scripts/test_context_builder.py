from app.graph.nodes.context_builder_node import build_generation_contexts


def main() -> None:
    contexts, metadata = build_generation_contexts(
        [
            {"chunk_id": "c1", "text": "第一条证据", "source": "a.pdf"},
            {"chunk_id": "c1", "text": "重复证据", "source": "a.pdf"},
            {"chunk_id": "c2", "text": "第二条证据内容较长", "source": "b.pdf"},
            {"chunk_id": "c3", "text": "超过条数限制", "source": "c.pdf"},
        ],
        max_items=2,
        max_chars=18,
    )
    assert [item["evidence_id"] for item in contexts] == ["E1", "E2"]
    assert contexts[0]["citation_label"] == "资料1"
    assert metadata["input_context_count"] == 4
    assert metadata["generation_context_count"] == 2
    assert metadata["generation_context_chars"] <= 18
    assert metadata["deduplicated_count"] >= 1
    assert metadata["truncated"] is True
    print("Context Builder test passed")


if __name__ == "__main__":
    main()
