from app.tools.sql_tool import IndustrialSQLTool


def main():
    tool = IndustrialSQLTool()

    questions = [
        "最近一周ZP8工位误识别数量是多少？",
        "哪个工位报警最多？",
        "AI视觉检测置信度低于0.7的记录有哪些？",
        "最近30天不同报警代码的数量是多少？",
        "质量案例中最常见的缺陷类型是什么？"
    ]

    for question in questions:
        print("=" * 80)
        print("question:", question)

        result = tool.run(question)

        print("sql:", result["sql"])
        print("row_count:", result["row_count"])
        print("rows:", result["rows"][:5])


if __name__ == "__main__":
    main()