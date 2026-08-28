from langgraph.graph import StateGraph, START, END

from app.graph.state import IndustrialRAGState
from app.graph.nodes.intent_router_node import (
    intent_router_node,
    route_after_intent,
)
from app.graph.nodes.query_rewriter_node import query_rewriter_node
from app.graph.nodes.retrieve_node import retrieve_node
from app.graph.nodes.sql_tool_node import sql_tool_node
from app.graph.nodes.evidence_judge_node import (
    evidence_judge_node,
    route_after_evidence_judge,
)
from app.graph.nodes.generate_node import generate_node
from app.graph.nodes.load_memory_node import load_memory_node
from app.graph.nodes.save_memory_node import save_memory_node
from app.graph.nodes.context_builder_node import context_builder_node
from app.graph.nodes.answer_verifier_node import answer_verifier_node
from app.graph.nodes.finalize_answer_node import finalize_answer_node


def build_industrial_rag_graph():
    graph = StateGraph(IndustrialRAGState)

    graph.add_node("load_memory", load_memory_node)
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("sql_tool", sql_tool_node)
    graph.add_node("query_rewriter", query_rewriter_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("evidence_judge", evidence_judge_node)
    graph.add_node("context_builder", context_builder_node)
    graph.add_node("generate", generate_node)
    graph.add_node("answer_verifier", answer_verifier_node)
    graph.add_node("finalize_answer", finalize_answer_node)
    graph.add_node("save_memory", save_memory_node)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "intent_router")

    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "sql": "sql_tool",
            "rag": "query_rewriter",
            "generate": "context_builder",
        }
    )

    graph.add_edge("sql_tool", "context_builder")
    graph.add_edge("query_rewriter", "retrieve")
    graph.add_edge("retrieve", "evidence_judge")

    graph.add_conditional_edges(
        "evidence_judge",
        route_after_evidence_judge,
        {
            "rewrite": "query_rewriter",
            "generate": "context_builder",
        }
    )

    graph.add_edge("context_builder", "generate")
    graph.add_edge("generate", "answer_verifier")
    graph.add_edge("answer_verifier", "finalize_answer")
    graph.add_edge("finalize_answer", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile()


industrial_rag_app = build_industrial_rag_graph()
