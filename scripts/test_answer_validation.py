from app.generation import validate_answer_citations


def main() -> None:
    contexts = [
        {
            "citation_label": "资料1",
            "text": "轮毂识别异常时，应优先检查相机曝光参数。",
        },
        {
            "citation_label": "资料2",
            "text": "光源角度变化可能降低图像对比度。",
        },
    ]

    valid, structure = validate_answer_citations(
        "- 优先检查相机曝光参数【资料1】。\n- 同时确认光源角度【资料2】。",
        contexts,
    )
    assert valid["passed"] is True
    assert valid["citation_coverage"] == 1.0
    assert len(structure["claims"]) == 2

    invalid, _ = validate_answer_citations(
        "- 优先检查相机曝光参数【资料9】。\n- 再检查模型版本。",
        contexts,
    )
    assert invalid["passed"] is False
    assert invalid["invalid_citation_ids"] == ["资料9"]
    assert invalid["citation_coverage"] == 0.0

    general, _ = validate_answer_citations(
        "你好，我可以帮助查询工业质量知识。",
        [],
        validation_required=False,
    )
    assert general["passed"] is True
    print("Answer citation validation test passed")


if __name__ == "__main__":
    main()
