from app.generation import is_abstention_answer
from app.graph.nodes.finalize_answer_node import finalize_answer_node


def main() -> None:
    assert is_abstention_answer(
        "根据提供的参考资料，未发现关于该车型热失控阈值的任何信息【资料1】。"
    )
    assert is_abstention_answer(
        "知识库中**未提供**关于某未上传车型高压电池热失控的具体温度阈值和处置标准的信息【资料1】。"
    )
    assert is_abstention_answer("当前资料未提及所需的处置标准。")
    assert not is_abstention_answer("检查完成，未发现异常【资料1】。")
    assert not is_abstention_answer("该标准要求温度不得超过80℃【资料1】。")
    assert is_abstention_answer(
        "- 资料不含高压电池热失控相关内容【资料1】。\n"
        "- 现有章节未提及温度阈值【资料2】。\n"
        "- 设备要求未涉及处置标准【资料3】。"
    )
    assert not is_abstention_answer(
        "- 标准要求温度不得超过80℃【资料1】。\n"
        "- 当前资料未提供售后处置流程【资料2】。"
    )

    state = {
        "draft_answer": "当前资料未提及该车型的热失控处置标准【资料1】。",
        "answer": "",
        "answer_abstained": False,
        "generation_quality_passed": True,
        "answer_validation": {"passed": True},
        "answer_structure": {},
        "missing_aspects": [],
    }
    result = finalize_answer_node(state)
    assert result["answer_abstained"] is True
    assert result["abstain_reason"]
    print("Semantic abstention classification tests passed")


if __name__ == "__main__":
    main()
