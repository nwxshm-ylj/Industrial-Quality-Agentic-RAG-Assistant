from app.graph.state import IndustrialRAGState
from app.tools.case_tool import IndustrialCaseTool


case_tool = IndustrialCaseTool()


def case_retriever_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    top_k = state.get("top_k", 5)

    try:
        case_result = case_tool.search_cases(
            question=question,
            limit=top_k,
        )

        context = case_tool.format_cases_as_context(case_result)

        citation = {
            "source": context.get("source"),
            "doc_type": context.get("doc_type"),
            "chunk_id": context.get("chunk_id"),
            "score": context.get("score"),
        }

        print("=" * 80)
        print("case_retriever_node 检索完成")
        print("question:", question)
        print("defect_type:", case_result.get("defect_type"))
        print("station:", case_result.get("station"))
        print("row_count:", case_result.get("row_count"))
        print("=" * 80)

        return {
            "case_result": case_result,
            "contexts": [context],
            "citations": [citation],
        }

    except Exception as e:
        print("=" * 80)
        print("case_retriever_node 检索失败")
        print("question:", question)
        print("error:", repr(e))
        print("=" * 80)

        fallback_context = {
            "text": f"历史案例检索失败，错误信息：{str(e)}",
            "source": "PostgreSQL.quality_cases",
            "doc_type": "CASE_ERROR",
            "chunk_id": "case_error",
            "score": 0.0,
        }

        return {
            "case_result": {
                "question": question,
                "rows": [],
                "row_count": 0,
                "error": str(e),
            },
            "contexts": [fallback_context],
            "citations": [
                {
                    "source": "PostgreSQL.quality_cases",
                    "doc_type": "CASE_ERROR",
                    "chunk_id": "case_error",
                    "score": 0.0,
                }
            ],
        }