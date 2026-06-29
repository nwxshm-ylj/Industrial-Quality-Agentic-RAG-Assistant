from langgraph.graph import StateGraph, START, END

from app.graph.state import IndustrialRAGState
from app.graph.nodes.intent_router_node import (
    intent_router_node,
    route_after_intent,
)
from app.graph.nodes.query_rewriter_node import query_rewriter_node
from app.graph.nodes.retrieve_node import retrieve_node
from app.graph.nodes.rule_tool_node import (
    rule_tool_node,
    route_after_rule_tool,
)
from app.graph.nodes.sql_tool_node import sql_tool_node
from app.graph.nodes.case_retriever_node import case_retriever_node
from app.graph.nodes.evidence_judge_node import (
    evidence_judge_node,
    route_after_evidence_judge,
)
from app.graph.nodes.generate_node import generate_node


def build_industrial_rag_graph():
    graph = StateGraph(IndustrialRAGState)

    graph.add_node("intent_router", intent_router_node)
    graph.add_node("rule_tool", rule_tool_node)
    graph.add_node("sql_tool", sql_tool_node)
    graph.add_node("case_retriever", case_retriever_node)
    graph.add_node("query_rewriter", query_rewriter_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("evidence_judge", evidence_judge_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "intent_router")

    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "rule": "rule_tool",
            "sql": "sql_tool",
            "case": "case_retriever",
            "rag": "query_rewriter",
            "generate": "generate",
        }
    )

    graph.add_conditional_edges(
        "rule_tool",
        route_after_rule_tool,
        {
            "generate": "generate",
            "rag": "query_rewriter",
        }
    )

    graph.add_edge("sql_tool", "generate")
    graph.add_edge("case_retriever", "generate")

    graph.add_edge("query_rewriter", "retrieve")
    graph.add_edge("retrieve", "evidence_judge")

    graph.add_conditional_edges(
        "evidence_judge",
        route_after_evidence_judge,
        {
            "rewrite": "query_rewriter",
            "generate": "generate",
        }
    )

    graph.add_edge("generate", END)

    return graph.compile()


industrial_rag_app = build_industrial_rag_graph()