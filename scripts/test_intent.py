from app.graph.nodes.intent_router_node import intent_router_node


def main():
    questions = [
        "轮毂识别异常可能是什么原因？",
        "扭矩工位连续报警应该怎么排查？",
        "有没有历史上类似的OCR识别失败案例？",
        "PR001对应什么轮毂配置？",
        "最近一周ZP8工位误识别数量是多少？",
        "你是谁？"
    ]

    for question in questions:
        state = {
            "question": question,
            "intent": "doc_qa",
            "rewritten_query": "",
            "contexts": [],
            "answer": "",
            "citations": [],
            "evidence_score": 0.0,
            "evidence_enough": False,
            "retry_count": 0,
            "top_k": 5,
        }

        result = intent_router_node(state)

        print("=" * 80)
        print("question:", question)
        print("intent:", result["intent"])


if __name__ == "__main__":
    main()