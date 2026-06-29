from app.graph.state import IndustrialRAGState
from app.tools.sql_tool import IndustrialSQLTool


sql_tool = IndustrialSQLTool()


def sql_tool_node(state: IndustrialRAGState) -> dict:
    question = state["question"]

    try:
        sql_result = sql_tool.run(question)
        context = sql_tool.format_sql_result_as_context(sql_result)

        citation = {
            "source": context.get("source"),
            "doc_type": context.get("doc_type"),
            "chunk_id": context.get("chunk_id"),
            "score": context.get("score"),
        }

        print("=" * 80)
        print("sql_tool_node 查询完成")
        print("question:", question)
        print("sql:", sql_result.get("sql"))
        print("row_count:", sql_result.get("row_count"))
        print("=" * 80)

        return {
            "sql_result": sql_result,
            "contexts": [context],
            "citations": [citation],
        }

    except Exception as e:
        print("=" * 80)
        print("sql_tool_node 查询失败")
        print("question:", question)
        print("error:", repr(e))
        print("=" * 80)

        fallback_context = {
            "text": f"SQL查询失败，错误信息：{str(e)}",
            "source": "PostgreSQL",
            "doc_type": "SQL_ERROR",
            "chunk_id": "sql_error",
            "score": 0.0,
        }

        return {
            "sql_result": {
                "question": question,
                "sql": "",
                "rows": [],
                "row_count": 0,
                "error": str(e),
            },
            "contexts": [fallback_context],
            "citations": [
                {
                    "source": "PostgreSQL",
                    "doc_type": "SQL_ERROR",
                    "chunk_id": "sql_error",
                    "score": 0.0,
                }
            ],
        }