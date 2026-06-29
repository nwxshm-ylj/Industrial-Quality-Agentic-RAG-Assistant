# scripts/test_chain.py

from app.rag.chain import IndustrialRAGChain


def main():
    chain = IndustrialRAGChain()

    result = chain.invoke(
        question="轮毂识别异常可能是什么原因？",
        top_k=3
    )

    print("=" * 80)
    print("question:", result.get("question"))
    print("answer:", repr(result.get("answer")))
    print("citations:", result.get("citations"))
    print("=" * 80)


if __name__ == "__main__":
    main()