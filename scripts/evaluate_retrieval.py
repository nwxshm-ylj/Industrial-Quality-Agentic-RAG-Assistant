from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.retrieval_evaluator import RetrievalEvaluator


DEFAULT_DATASET = Path("data/eval/retrieval_eval_questions.json")
DEFAULT_REPORT = Path("data/eval/retrieval_eval_report.json")


def parse_k_values(value: str) -> list[int]:
    try:
        result = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "k-values must be comma-separated integers"
        ) from exc
    if not result:
        raise argparse.ArgumentTypeError("k-values cannot be empty")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate online Qdrant + OpenSearch retrieval without invoking "
            "the answer-generating LLM. Query embeddings use the configured "
            "EmbeddingProvider."
        )
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--k-values", type=parse_k_values, default=[1, 3, 5])
    parser.add_argument("--max-questions", type=int, default=None)
    args = parser.parse_args()

    evaluator = RetrievalEvaluator()
    items = evaluator.load_dataset(args.dataset)
    report = evaluator.run(
        items,
        top_k=args.top_k,
        k_values=args.k_values,
        max_questions=args.max_questions,
        dataset_name=args.dataset.name,
    )
    versioned_path = args.output.with_name(
        f"{args.output.stem}_{report['run_id']}{args.output.suffix}"
    )
    report["report_path"] = versioned_path.as_posix()
    evaluator.write_report(report, versioned_path)
    evaluator.write_report(report, args.output)

    print(json.dumps({
        "run_id": report["run_id"],
        "status": report["status"],
        "summary": report["summary"],
        "metrics": report["metrics"],
        "latency": report["latency"],
        "report_path": versioned_path.as_posix(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
