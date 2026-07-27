from app.core.config import settings
from app.core.logger import log_business_event, observe_node
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

        contexts = [context]
        citations = [citation]
        graph_metadata = {
            "knowledge_graph_enabled": settings.knowledge_graph_enabled,
            "knowledge_graph_degraded": False,
            "knowledge_graph_path_count": 0,
        }
        if settings.knowledge_graph_enabled:
            try:
                from app.knowledge_graph.service import (
                    get_knowledge_graph_service,
                )

                graph_result = get_knowledge_graph_service().search_cases(
                    question,
                    limit=settings.knowledge_graph_result_limit,
                )
                if graph_result["path_count"]:
                    graph_context = {
                        "text": graph_result["context"],
                        "source": "Neo4j.quality_case_graph",
                        "doc_type": "KNOWLEDGE_GRAPH",
                        "chunk_id": "knowledge_graph_paths",
                        "score": 1.0,
                    }
                    contexts.append(graph_context)
                    citations.append(
                        {
                            "source": graph_context["source"],
                            "doc_type": graph_context["doc_type"],
                            "chunk_id": graph_context["chunk_id"],
                            "score": graph_context["score"],
                            "retrieval_source": "knowledge_graph",
                        }
                    )
                case_result["knowledge_graph"] = graph_result
                graph_metadata["knowledge_graph_path_count"] = graph_result[
                    "path_count"
                ]
            except Exception as graph_error:
                graph_metadata["knowledge_graph_degraded"] = True
                graph_metadata["knowledge_graph_degraded_reason"] = str(
                    graph_error
                )
                log_business_event(
                    "knowledge_graph_degraded",
                    status="degraded",
                    error_message=str(graph_error),
                )


        return {
            "case_result": case_result,
            "contexts": contexts,
            "citations": citations,
            "knowledge_graph_metadata": graph_metadata,
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
