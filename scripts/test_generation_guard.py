import app.graph.nodes.generate_node as generate_module


class FailingGenerator:
    def generate(self, **kwargs):
        raise AssertionError("证据不足时不应调用 LLM")


class CapturingGenerator:
    def __init__(self) -> None:
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return "规则要求见【资料1】。"


def main() -> None:
    original = generate_module.generator
    try:
        generate_module.generator = FailingGenerator()
        refused = generate_module.generate_node(
            {
                "question": "未知故障的原因是什么？",
                "intent": "rag",
                "generation_contexts": [],
                "contexts": [],
                "evidence_enough": False,
                "evidence_confidence": 0.12,
                "missing_aspects": ["原因"],
                "abstain_reason": "现有资料缺少原因证据",
                "rule_result": None,
                "sql_result": None,
                "memory_messages": [],
            }
        )
        assert refused["answer_abstained"] is True
        assert "无法可靠回答" in refused["answer"]

        capturing = CapturingGenerator()
        generate_module.generator = capturing
        generated = generate_module.generate_node(
            {
                "question": "该规则要求是什么？",
                "intent": "rag",
                "generation_contexts": [
                    {"text": "规则要求", "citation_label": "资料1"}
                ],
                "contexts": [],
                "evidence_enough": False,
                "evidence_confidence": 0.0,
                "missing_aspects": [],
                "rule_result": {"id": "rule-1"},
                "sql_result": None,
                "memory_messages": [],
            }
        )
        assert generated["answer_abstained"] is False
        assert capturing.kwargs["evidence_enough"] is True
        print("Generation trust guard test passed")
    finally:
        generate_module.generator = original


if __name__ == "__main__":
    main()
