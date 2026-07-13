from time import perf_counter
from uuid import uuid4

from app.core.logger import log_node_event
from app.graph.workflow import industrial_rag_app


class IndustrialGraphRAGChain:
    def invoke(
        self,
        question: str,
        top_k: int = 5,
        session_id: str = "default",
        request_id: str | None = None,
        user: dict | None = None,
    ) -> dict:
        request_id = request_id or str(uuid4())
        session_id = session_id or "default"
        initial_state = {
            "question": question,
            "request_id": request_id,
            "session_id": session_id,
            "user": user,
            "memory_messages": [],
            "intent": "doc_qa",
            "rewritten_query": "",
            "contexts": [],
            "answer": "",
            "citations": [],
            "retrieval_metadata": {},
            "evidence_score": 0.0,
            "evidence_enough": False,
            "retry_count": 0,
            "top_k": top_k,
            "rule_result": None,
            "sql_result": None,
            "case_result": None,
        }
        started_at = perf_counter()

        try:
            result = industrial_rag_app.invoke(initial_state)
        except Exception as exc:
            log_node_event(
                state=initial_state,
                node_name="graph_chat",
                latency_ms=(perf_counter() - started_at) * 1000,
                status="error",
                error=str(exc),
                exc_info=True,
            )
            raise

        total_latency_ms = round((perf_counter() - started_at) * 1000, 2)
        metadata = {
            "intent": result.get("intent"),
            "evidence_score": result.get("evidence_score"),
            "evidence_enough": result.get("evidence_enough"),
            "retry_count": result.get("retry_count"),
            "total_latency_ms": total_latency_ms,
        }
        metadata.update(result.get("retrieval_metadata", {}))

        log_node_event(
            state=result,
            node_name="graph_chat",
            latency_ms=total_latency_ms,
            status="success",
            intent=result.get("intent"),
        )

        return {
            "question": result.get("question", question),
            "answer": result.get("answer", ""),
            "citations": result.get("citations", []),
            "request_id": result.get("request_id", request_id),
            "session_id": result.get("session_id", session_id),
            "memory_messages": result.get("memory_messages", []),
            "metadata": metadata,

            "intent": result.get("intent"),
            "rewritten_query": result.get("rewritten_query"),
            "evidence_score": result.get("evidence_score"),
            "evidence_enough": result.get("evidence_enough"),
            "retry_count": result.get("retry_count"),

            "rule_result": result.get("rule_result"),
            "sql_result": result.get("sql_result"),
            "case_result": result.get("case_result"),
            "contexts": result.get("contexts", []),
        }
