from app.generation import validate_answer_citations


def main() -> None:
    contexts = [
        {"citation_label": "资料1", "text": "应优先检查相机曝光参数。"},
        {"citation_label": "资料2", "text": "光源角度会影响图像对比度。"},
    ]
    valid, structure = validate_answer_citations(
        "### 排查建议\n"
        "- 优先检查相机曝光参数【资料1】。\n"
        "- 同时确认光源角度【资料2】。",
        contexts,
    )
    assert valid["passed"] is True
    assert valid["citation_validation_mode"] == "line_reference_only"
    assert valid["line_count"] == 2
    assert valid["claim_count"] == 2
    assert len(structure["claims"]) == 2
    assert all(claim["citation_required"] for claim in structure["claims"])

    invalid, invalid_structure = validate_answer_citations(
        "- 优先检查相机曝光参数【资料9】。\n- 再检查模型版本。",
        contexts,
    )
    assert invalid["passed"] is False
    assert invalid["invalid_citation_ids"] == ["资料9"]
    assert invalid["uncited_line_count"] == 1
    assert invalid["cited_line_count"] == 0
    assert len(invalid_structure["lines"]) == 2

    general, _ = validate_answer_citations(
        "你好，我可以帮助查询工业质量知识。",
        [],
        validation_required=False,
    )
    assert general["passed"] is True
    print("Answer line citation validation test passed")


if __name__ == "__main__":
    main()
