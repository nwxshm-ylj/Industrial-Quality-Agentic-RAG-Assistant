from app.core.logger import observe_node
from app.graph.state import IndustrialRAGState
from app.tools.case_tool import IndustrialCaseTool


case_tool = IndustrialCaseTool()


@observe_node("case_retriever")
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


        return {
            "case_result": case_result,
            "contexts": [context],
            "citations": [citation],
        }

    except Exception as e:
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