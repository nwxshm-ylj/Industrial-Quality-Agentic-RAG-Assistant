from app.tools.case_tool import IndustrialCaseTool


def main():
    tool = IndustrialCaseTool()

    questions = [
        "历史上有没有类似的轮毂误识别案例？",
        "OCR VIN识别失败之前怎么处理的？",
        "扭矩报警有没有复发案例？",
        "ZP8工位有没有历史质量案例？",
        "有没有配置不一致的历史案例？",
    ]

    for question in questions:
        print("=" * 80)
        print("question:", question)

        result = tool.search_cases(
            question=question,
            limit=5,
        )

        print("defect_type:", result.get("defect_type"))
        print("station:", result.get("station"))
        print("row_count:", result.get("row_count"))
        print("rows:", result.get("rows")[:3])

        context = tool.format_cases_as_context(result)
        print("context:", context)


if __name__ == "__main__":
    main()