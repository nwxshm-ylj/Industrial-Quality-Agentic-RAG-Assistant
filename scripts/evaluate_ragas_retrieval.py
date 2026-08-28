from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.evaluation.retrieval_evaluator import RetrievalEvaluator


DEFAULT_OUTPUT = Path("data/eval/ragas_grounding_retrieval_report.json")


def load_ragas_retrieval_items(
    path: Path,
    *,
    relevance_field: str,
    question_ids: set[str] | None = None,
) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("RAGAS dataset must be a non-empty JSON list")

    items = []
    for item in payload:
        item_id = str(item.get("id") or "").strip()
        if question_ids and item_id not in question_ids:
            continue
        expected_field = (
            "expected_chunk_ids"
            if relevance_field == "chunk_id"
            else "expected_doc_ids"
        )
        relevant_ids = item.get(expected_field)
        if not isinstance(relevant_ids, list) or not relevant_ids:
            raise ValueError(
                f"RAGAS item {item.get('id')} must define {expected_field}"
            )
        items.append(
            {
                "id": item_id,
                "category": "ragas_grounding",
                "question": item["question"],
                "relevance_field": relevance_field,
                "relevant_ids": relevant_ids,
            }
        )
    if question_ids:
        found_ids = {item["id"] for item in items}
        unknown_ids = question_ids - found_ids
        if unknown_ids:
            raise ValueError(
                "Unknown question ids: " + ", ".join(sorted(unknown_ids))
            )
    if not items:
        raise ValueError("No retrieval evaluation items selected")
    return items


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval for the grounded RAGAS gold dataset"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(settings.ragas_dataset_path),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--k-values", default="1,3,5")
    parser.add_argument(
        "--relevance-field",
        choices=("doc_id", "chunk_id"),
        default="doc_id",
    )
    parser.add_argument(
        "--question-ids",
        default="",
        help="Comma-separated question ids for a targeted regression run",
    )
    args = parser.parse_args()
    output_path = args.output
    if (
        output_path == DEFAULT_OUTPUT
        and args.relevance_field == "chunk_id"
    ):
        output_path = Path("data/eval/ragas_grounding_chunk_retrieval_report.json")

    k_values = [
        int(value.strip())
        for value in args.k_values.split(",")
        if value.strip()
    ]
    question_ids = {
        value.strip()
        for value in args.question_ids.split(",")
        if value.strip()
    }
    evaluator = RetrievalEvaluator()
    report = evaluator.run(
        load_ragas_retrieval_items(
            args.dataset,
            relevance_field=args.relevance_field,
            question_ids=question_ids or None,
        ),
        top_k=args.top_k,
        k_values=k_values,
        dataset_name=f"{args.dataset.name}:{args.relevance_field}",
    )
    versioned_path = output_path.with_name(
        f"{output_path.stem}_{report['run_id']}{output_path.suffix}"
    )
    report["report_path"] = versioned_path.as_posix()
    evaluator.write_report(report, versioned_path)
    evaluator.write_report(report, output_path)
    print(
        json.dumps(
            {
                "run_id": report["run_id"],
                "status": report["status"],
                "summary": report["summary"],
                "metrics": report["metrics"],
                "latency": report["latency"],
                "report_path": versioned_path.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
