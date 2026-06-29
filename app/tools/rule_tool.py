from pathlib import Path
from typing import Any

import yaml


class IndustrialRuleTool:
    def __init__(self, rule_path: str = "data/rules/industrial_rules.yaml"):
        self.rule_path = Path(rule_path)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict[str, Any]:
        if not self.rule_path.exists():
            raise FileNotFoundError(f"规则文件不存在: {self.rule_path}")

        with self.rule_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def search_rules(self, question: str) -> dict[str, Any] | None:
        """
        第一版采用关键词匹配。
        后续可以升级为：
        1. 规则向量化检索；
        2. LLM 判断规则匹配；
        3. BM25 + 规则库检索。
        """
        question_lower = question.lower()

        pr_result = self._search_pr_rules(question_lower)
        if pr_result:
            return pr_result

        fault_result = self._search_fault_rules(question_lower)
        if fault_result:
            return fault_result

        return None

    def _search_pr_rules(self, question_lower: str) -> dict[str, Any] | None:
        pr_rules = self.rules.get("pr_rules", {})

        for category, items in pr_rules.items():
            for pr_code, info in items.items():
                if pr_code.lower() in question_lower:
                    return {
                        "rule_type": "pr_rule",
                        "category": category,
                        "rule_id": pr_code,
                        "content": info,
                    }

        return None

    def _search_fault_rules(self, question_lower: str) -> dict[str, Any] | None:
        fault_rules = self.rules.get("fault_rules", {})

        for rule_id, rule in fault_rules.items():
            keywords = rule.get("keywords", [])

            for keyword in keywords:
                if keyword.lower() in question_lower:
                    return {
                        "rule_type": "fault_rule",
                        "rule_id": rule_id,
                        "content": rule,
                    }

        return None

    def format_rule_as_context(self, rule_result: dict[str, Any]) -> dict:
        """
        将规则结果转成和 RAG contexts 类似的数据结构，
        这样后续 generate_node 可以复用原来的 AnswerGenerator。
        """
        rule_type = rule_result.get("rule_type", "")
        rule_id = rule_result.get("rule_id", "")
        content = rule_result.get("content", {})

        if rule_type == "pr_rule":
            text = f"""
规则类型：PR配置规则
规则编号：{rule_id}
配置名称：{content.get("name")}
关联对象：{content.get("part")}
说明：{content.get("description")}
"""
        else:
            text = f"""
规则类型：故障排查规则
规则编号：{rule_id}
规则名称：{content.get("name")}

可能原因：
{self._format_list(content.get("possible_causes", []))}

排查步骤：
{self._format_list(content.get("check_steps", []))}

处理建议：
{self._format_list(content.get("action", []))}
"""

        return {
            "text": text.strip(),
            "source": "industrial_rules.yaml",
            "doc_type": "RULE",
            "chunk_id": rule_id,
            "score": 1.0,
        }

    @staticmethod
    def _format_list(items: list[str]) -> str:
        if not items:
            return "无"

        return "\n".join(
            f"{idx}. {item}"
            for idx, item in enumerate(items, start=1)
        )