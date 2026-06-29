from app.rag.graph_chain import IndustrialGraphRAGChain


def main():
    chain = IndustrialGraphRAGChain()

    questions = [
        "历史上有没有类似的轮毂误识别案例？",
        "OCR VIN识别失败之前怎么处理的？",
        "扭矩报警有没有复发案例？",
        "最近一周ZP8工位误识别数量是多少？",
        "PR001对应什么轮毂配置？",
        "轮毂识别异常可能是什么原因？",
    ]

    for question in questions:
        result = chain.invoke(
            question=question,
            top_k=3,
        )

        print("=" * 80)
        print("question:", result["question"])
        print("answer:", result["answer"])
        print("citations:", result["citations"])


if __name__ == "__main__":
    main()