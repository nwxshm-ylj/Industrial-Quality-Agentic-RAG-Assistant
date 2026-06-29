from app.graph.workflow import industrial_rag_app


class IndustrialGraphRAGChain:
    def invoke(self, question: str, top_k: int = 5) -> dict:
        result = industrial_rag_app.invoke({
            "question": question,
            "intent": "doc_qa",
            "rewritten_query": "",
            "contexts": [],
            "answer": "",
            "citations": [],
            "evidence_score": 0.0,
            "evidence_enough": False,
            "retry_count": 0,
            "top_k": top_k,
            "rule_result": None,
            "sql_result": None,
            "case_result": None,
        })

        return {
            "question": result.get("question", question),
            "answer": result.get("answer", ""),
            "citations": result.get("citations", []),

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