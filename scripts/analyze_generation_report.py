from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.evaluation.generation_analysis import analyze_generation_results


REPORT_DIR = Path("data/eval")


def _latest_report() -> Path:
    candidates = sorted(
        REPORT_DIR.glob("eval_report_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("未找到 data/eval/eval_report_<run_id>.json")
    return candidates[0]


def analyze_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    results = report.get("results")
    if not isinstance(results, list):
        raise ValueError(f"评估报告缺少 results 数组: {path}")
    analysis = analyze_generation_results(
        [item for item in results if isinstance(item, dict)]
    )
    return {
        "run_id": report.get("run_id"),
        "report_path": path.as_posix(),
        "failure_analysis": analysis,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="分析生成式 RAG 评估失败原因")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="评估报告路径；不传时分析 data/eval 下最新报告",
    )
    args = parser.parse_args()
    result = analyze_report(args.report or _latest_report())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

