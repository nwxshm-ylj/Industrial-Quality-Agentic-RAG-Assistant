from app.graph.state import IndustrialRAGState
from app.rag.generator import AnswerGenerator


generator = AnswerGenerator()


def generate_node(state: IndustrialRAGState) -> dict:
    question = state["question"]
    contexts = state.get("contexts", [])
    intent = state.get("intent", "doc_qa")
    memory_messages = state.get("memory_messages", [])

    # 当前阶段：general 问题不走知识库，给出简短说明
    if intent == "general" and not contexts:
        answer = (
            "当前系统主要面向工业质量知识库、设备异常诊断、规则查询和质量数据分析。"
            "请提出与工业文档、质量异常、设备报警、AI视觉、OCR或扭矩监控相关的问题。"
        )
    else:
        answer = generator.generate(
            question=question,
            contexts=contexts,
            memory_messages=memory_messages,
        )

    print("=" * 80)
    print("generate_node 生成完成")
    print("intent:", intent)
    print("answer:", repr(answer[:200]))
    print("=" * 80)

    return {
        "answer": answer
    }