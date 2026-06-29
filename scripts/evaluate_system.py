import json
import time
from pathlib import Path
from typing import Any

from app.graph.workflow import industrial_rag_app


EVAL_FILE = "data/eval/eval_questions.json"
REPORT_FILE = "data/eval/eval_report.json"


def load_eval_questions(path: str = EVAL_FILE) -> list[dict[str, Any]]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"评估集不存在: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def invoke_graph(question: str, top_k: int = 3) -> dict[str, Any]:
    result = industrial_rag_app.invoke({
        "question": question,
        "intent": "doc_qa",
        "rewritten_query": "",
        "contexts": [],
        "answer": "",
        "citations": [],
        "evidence_score": 0.0,
        "evidence_enough": False,
        "retry_count": 0,
        "top_k": top_k,
        "rule_result": None,
        "sql_result": None,
        "case_result": None,
    })

    return result


def check_intent(result: dict[str, Any], expected_intent: str | None) -> bool:
    if expected_intent is None:
        return True

    actual_intent = result.get("intent")
    return actual_intent == expected_intent


def check_doc_type(result: dict[str, Any], expected_doc_type: str | None) -> bool:
    if expected_doc_type is None:
        return True

    citations = result.get("citations", [])

    for citation in citations:
        if citation.get("doc_type") == expected_doc_type:
            return True

    return False


def check_source(result: dict[str, Any], expected_source_contains: str | None) -> bool:
    if expected_source_contains is None:
        return True

    citations = result.get("citations", [])

    for citation in citations:
        source = str(citation.get("source", ""))
        if expected_source_contains.lower() in source.lower():
            return True

    return False


def check_answer_keywords(result: dict[str, Any], expected_keywords: list[str] | None) -> bool:
    if not expected_keywords:
        return True

    answer = str(result.get("answer", ""))

    hit_count = 0

    for keyword in expected_keywords:
        if keyword.lower() in answer.lower():
            hit_count += 1

    # 不要求全部命中，命中一半以上即可
    return hit_count >= max(1, len(expected_keywords) // 2)


def summarize_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []

    for citation in citations:
        summary.append({
            "source": citation.get("source"),
            "doc_type": citation.get("doc_type"),
            "chunk_id": citation.get("chunk_id"),
            "score": citation.get("score"),
            "retrieval_source": citation.get("retrieval_source"),
            "hybrid_score": citation.get("hybrid_score"),
            "rerank_score": citation.get("rerank_score"),
            "final_score_type": citation.get("final_score_type"),
        })

    return summary


def evaluate_one(item: dict[str, Any]) -> dict[str, Any]:
    question = item["question"]

    start = time.time()
    result = invoke_graph(question=question, top_k=3)
    latency = round(time.time() - start, 3)

    intent_ok = check_intent(
        result=result,
        expected_intent=item.get("expected_intent"),
    )

    doc_type_ok = check_doc_type(
        result=result,
        expected_doc_type=item.get("expected_doc_type"),
    )

    source_ok = check_source(
        result=result,
        expected_source_contains=item.get("expected_source_contains"),
    )

    answer_keywords_ok = check_answer_keywords(
        result=result,
        expected_keywords=item.get("expected_answer_keywords"),
    )

    all_ok = all([
        intent_ok,
        doc_type_ok,
        source_ok,
        answer_keywords_ok,
    ])

    return {
        "id": item.get("id"),
        "question": question,
        "expected_intent": item.get("expected_intent"),
        "actual_intent": result.get("intent"),
        "intent_ok": intent_ok,
        "doc_type_ok": doc_type_ok,
        "source_ok": source_ok,
        "answer_keywords_ok": answer_keywords_ok,
        "all_ok": all_ok,
        "latency_seconds": latency,
        "answer_preview": str(result.get("answer", ""))[:300],
        "citations": summarize_citations(result.get("citations", [])),
    }


def calculate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)

    if total == 0:
        return {}

    def rate(key: str) -> float:
        count = sum(1 for item in results if item.get(key))
        return round(count / total, 4)

    avg_latency = round(
        sum(item.get("latency_seconds", 0.0) for item in results) / total,
        3
    )

    metrics = {
        "total": total,
        "overall_pass_rate": rate("all_ok"),
        "intent_accuracy": rate("intent_ok"),
        "doc_type_accuracy": rate("doc_type_ok"),
        "source_accuracy": rate("source_ok"),
        "answer_keyword_hit_rate": rate("answer_keywords_ok"),
        "avg_latency_seconds": avg_latency,
    }

    return metrics


def main():
    eval_questions = load_eval_questions()

    results = []

    for idx, item in enumerate(eval_questions, start=1):
        print("=" * 100)
        print(f"评估进度: {idx}/{len(eval_questions)}")
        print("question:", item["question"])

        try:
            eval_result = evaluate_one(item)
            results.append(eval_result)

            print("actual_intent:", eval_result["actual_intent"])
            print("intent_ok:", eval_result["intent_ok"])
            print("doc_type_ok:", eval_result["doc_type_ok"])
            print("source_ok:", eval_result["source_ok"])
            print("answer_keywords_ok:", eval_result["answer_keywords_ok"])
            print("all_ok:", eval_result["all_ok"])
            print("latency_seconds:", eval_result["latency_seconds"])

        except Exception as e:
            error_result = {
                "id": item.get("id"),
                "question": item.get("question"),
                "error": str(e),
                "all_ok": False,
                "intent_ok": False,
                "doc_type_ok": False,
                "source_ok": False,
                "answer_keywords_ok": False,
                "latency_seconds": None,
            }

            results.append(error_result)

            print("评估失败:", repr(e))

    metrics = calculate_metrics(results)

    report = {
        "metrics": metrics,
        "results": results,
    }

    report_path = Path(REPORT_FILE)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("=" * 100)
    print("评估完成")
    print("metrics:")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"评估报告已保存: {REPORT_FILE}")


if __name__ == "__main__":
    main()