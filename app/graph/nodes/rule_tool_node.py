from app.graph.state import IndustrialRAGState
from app.tools.rule_tool import IndustrialRuleTool


rule_tool = IndustrialRuleTool()


def rule_tool_node(state: IndustrialRAGState) -> dict:
    question = state["question"]

    rule_result = rule_tool.search_rules(question)

    if not rule_result:
        print("=" * 80)
        print("rule_tool_node 未匹配到规则")
        print("question:", question)
        print("=" * 80)

        return {
            "rule_result": None,
            "contexts": [],
            "citations": []
        }

    context = rule_tool.format_rule_as_context(rule_result)

    citation = {
        "source": context.get("source"),
        "doc_type": context.get("doc_type"),
        "chunk_id": context.get("chunk_id"),
        "score": context.get("score"),
    }

    print("=" * 80)
    print("rule_tool_node 匹配到规则")
    print("question:", question)
    print("rule_type:", rule_result.get("rule_type"))
    print("rule_id:", rule_result.get("rule_id"))
    print("=" * 80)

    return {
        "rule_result": rule_result,
        "contexts": [context],
        "citations": [citation]
    }


def route_after_rule_tool(state: IndustrialRAGState) -> str:
    """
    如果规则匹配成功，直接生成答案。
    如果规则没有匹配到，则回退到 RAG 检索路径。
    """
    rule_result = state.get("rule_result")

    if rule_result:
        return "generate"

    return "rag"