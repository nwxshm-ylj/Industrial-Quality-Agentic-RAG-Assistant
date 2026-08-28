"""Compare two generation-evaluation reports and produce release evidence.

The script is intentionally dependency-free so it can run on the host or in
the API container. It never calls an LLM or an embedding service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


METRICS = (
    ("overall_pass_rate", "总体通过率", "rate"),
    ("source_hit_rate", "来源命中率", "rate"),
    ("answer_keyword_hit_rate", "答案关键词命中率", "rate"),
    ("citation_validation_pass_rate", "引用验证通过率", "rate"),
    ("semantic_support_pass_rate", "语义支持通过率", "rate"),
    ("abstention_accuracy", "拒答准确率", "rate"),
    ("repair_trigger_rate", "实际修复触发率", "rate"),
    ("llm_repair_selection_rate", "LLM 修复选择率", "rate"),
    ("deterministic_prune_selection_rate", "确定性裁剪选择率", "rate"),
    ("repair_avoidance_rate", "避免修复率", "rate"),
    ("avg_latency_ms", "平均延迟", "latency"),
    ("p95_latency_ms", "P95 延迟", "latency"),
    ("avg_latency_llm_repair_ms", "修复路径平均延迟", "latency"),
    (
        "avg_latency_without_llm_repair_ms",
        "非修复路径平均延迟",
        "latency",
    ),
)


def load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"评测报告不存在: {path}")
    with path.open("r", encoding="utf-8") as file:
        report = json.load(file)
    if not isinstance(report.get("metrics"), dict):
        raise ValueError(f"评测报告缺少 metrics: {path}")
    if not isinstance(report.get("results"), list):
        raise ValueError(f"评测报告缺少 results: {path}")
    return report


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def format_value(value: Any, kind: str) -> str:
    if value is None:
        return "--"
    number = float(value)
    if kind == "rate":
        return f"{number * 100:.2f}%"
    return f"{number:.2f} ms"


def format_delta(baseline: Any, candidate: Any, kind: str) -> str:
    if baseline is None or candidate is None:
        return "--"
    delta = float(candidate) - float(baseline)
    if kind == "rate":
        return f"{delta * 100:+.2f} pp"
    return f"{delta:+.2f} ms"


def action_counts(report: dict[str, Any]) -> Counter[str]:
    actions: Counter[str] = Counter()
    for item in report["results"]:
        action = item.get("validation_action")
        if not action:
            history = item.get("answer_validation_history") or []
            if history and isinstance(history[0], dict):
                action = history[0].get("recommended_action")
        if action:
            actions[str(action)] += 1
    return actions


def metric_number(
    metrics: dict[str, Any], key: str, *, default: float
) -> float:
    value = metrics.get(key)
    return default if value is None else float(value)


def build_gates(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> list[dict[str, Any]]:
    baseline_metrics = baseline["metrics"]
    metrics = candidate["metrics"]
    baseline_pass = metric_number(
        baseline_metrics, "overall_pass_rate", default=0.0
    )
    error_count = sum(1 for item in candidate["results"] if item.get("error"))
    definitions = (
        (
            "总体通过率不回退",
            metric_number(metrics, "overall_pass_rate", default=0.0)
            >= baseline_pass,
            f">= {baseline_pass * 100:.2f}%",
            format_value(metrics.get("overall_pass_rate"), "rate"),
        ),
        (
            "引用验证通过率",
            metric_number(
                metrics, "citation_validation_pass_rate", default=0.0
            )
            >= 0.95,
            ">= 95.00%",
            format_value(metrics.get("citation_validation_pass_rate"), "rate"),
        ),
        (
            "语义支持通过率",
            metric_number(metrics, "semantic_support_pass_rate", default=0.0)
            >= 0.95,
            ">= 95.00%",
            format_value(metrics.get("semantic_support_pass_rate"), "rate"),
        ),
        (
            "拒答准确率",
            metric_number(metrics, "abstention_accuracy", default=0.0) >= 0.95,
            ">= 95.00%",
            format_value(metrics.get("abstention_accuracy"), "rate"),
        ),
        (
            "LLM 修复选择率",
            metric_number(metrics, "llm_repair_selection_rate", default=1.0)
            <= 0.30,
            "<= 30.00%",
            format_value(metrics.get("llm_repair_selection_rate"), "rate"),
        ),
        (
            "平均延迟",
            metric_number(metrics, "avg_latency_ms", default=float("inf"))
            <= 15000,
            "<= 15000 ms",
            format_value(metrics.get("avg_latency_ms"), "latency"),
        ),
        (
            "P95 延迟",
            metric_number(metrics, "p95_latency_ms", default=float("inf"))
            <= 30000,
            "<= 30000 ms",
            format_value(metrics.get("p95_latency_ms"), "latency"),
        ),
        ("评测执行错误", error_count == 0, "= 0", str(error_count)),
    )
    return [
        {"name": name, "passed": passed, "target": target, "actual": actual}
        for name, passed, target, actual in definitions
    ]


def build_markdown(
    baseline_path: Path,
    candidate_path: Path,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> str:
    gates = build_gates(baseline, candidate)
    passed = all(item["passed"] for item in gates)
    lines = [
        "# Phase G3.5 生成质量与延迟验收报告",
        "",
        f"结论：**{'通过' if passed else '未通过'}**",
        "",
        "## 报告身份",
        "",
        f"- 基线报告：`{baseline_path.as_posix()}`",
        f"- 基线 SHA256：`{file_sha256(baseline_path)}`",
        f"- 候选报告：`{candidate_path.as_posix()}`",
        f"- 候选 SHA256：`{file_sha256(candidate_path)}`",
        "",
        "## 核心指标对比",
        "",
        "| 指标 | 基线 | 候选版本 | 变化 |",
        "|---|---:|---:|---:|",
    ]
    baseline_metrics = baseline["metrics"]
    candidate_metrics = candidate["metrics"]
    for key, label, kind in METRICS:
        old = baseline_metrics.get(key)
        new = candidate_metrics.get(key)
        lines.append(
            f"| {label} | {format_value(old, kind)} | "
            f"{format_value(new, kind)} | {format_delta(old, new, kind)} |"
        )

    lines.extend(
        [
            "",
            "## 验收门槛",
            "",
            "| 验收项 | 目标 | 实际 | 结果 |",
            "|---|---:|---:|---|",
        ]
    )
    for gate in gates:
        lines.append(
            f"| {gate['name']} | {gate['target']} | {gate['actual']} | "
            f"{'PASS' if gate['passed'] else 'FAIL'} |"
        )

    actions = action_counts(candidate)
    failed_ids = [
        str(item.get("id"))
        for item in candidate["results"]
        if not item.get("all_ok", False)
    ]
    lines.extend(
        [
            "",
            "## 路径分布与失败样本",
            "",
            f"- 直接结束：{actions.get('finalize', 0)}",
            f"- 确定性裁剪：{actions.get('deterministic_prune', 0)}",
            f"- LLM 修复：{actions.get('llm_repair', 0)}",
            f"- 失败题目：{', '.join(failed_ids) if failed_ids else '无'}",
            "",
            "## 判定说明",
            "",
            "只有候选版本同时满足质量不回退、语义与引用校验、拒答安全、修复率和延迟门槛，才判定为通过。",
            "本报告只证明当前评测集与当前环境下的结果，不代表生产流量中的绝对性能。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="对比两份生成评测报告")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/eval/generation_acceptance_report.md"),
    )
    args = parser.parse_args()

    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)
    markdown = build_markdown(
        args.baseline,
        args.candidate,
        baseline,
        candidate,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\n验收报告已保存: {args.output}")


if __name__ == "__main__":
    main()
