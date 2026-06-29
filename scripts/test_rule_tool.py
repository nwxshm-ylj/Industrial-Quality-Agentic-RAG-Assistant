from app.tools.rule_tool import IndustrialRuleTool


def main():
    tool = IndustrialRuleTool()

    questions = [
        "PR001对应什么轮毂配置？",
        "PR102是什么后视镜配置？",
        "轮毂识别异常有哪些排查规则？",
        "合格证OCR识别VIN失败怎么办？",
        "扭矩工位连续报警应该怎么处理？",
        "没有任何规则的问题"
    ]

    for question in questions:
        result = tool.search_rules(question)

        print("=" * 80)
        print("question:", question)
        print("result:", result)

        if result:
            context = tool.format_rule_as_context(result)
            print("context:", context)


if __name__ == "__main__":
    main()