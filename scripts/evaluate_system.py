import json
import hashlib
import math
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.evaluation.generation_analysis import classify_generation_result
from app.graph.workflow import industrial_rag_app
from app.graph.query_features import normalize_intent_label
from app.prompting import get_prompt_registry
from app.traceability.taxonomy import normalize_document_type


EVAL_FILE = "data/eval/eval_questions.json"
REPORT_FILE = "data/eval/eval_report.json"


def build_evaluation_fingerprint(
    dataset_path: str = EVAL_FILE,
) -> dict[str, Any]:
    path = Path(dataset_path)
    dataset_hash = (
        hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    )
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        git_commit = None
    return {
        "dataset_path": path.as_posix(),
        "dataset_sha256": dataset_hash,
        "git_commit": git_commit,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": (
            settings.local_embedding_model_name
            if settings.embedding_provider == "local"
            else settings.qwen_embedding_model
        ),
        "embedding_dimension": (
            settings.local_embedding_dimension
            if settings.embedding_provider == "local"
            else settings.qwen_embedding_dimension
        ),
        "embedding_index_version": settings.embedding_index_version,
        "qdrant_collection": settings.qdrant_collection,
        "qdrant_collection_alias": settings.qdrant_collection_alias,
        "opensearch_index_prefix": settings.opensearch_index_prefix,
        "keyword_index_version": settings.keyword_index_version,
        "retrieval_fusion_strategy": settings.retrieval_fusion_strategy,
        "reranker_enabled": settings.use_reranker,
        "reranker_model": settings.reranker_model,
        "evidence_confidence_threshold": settings.evidence_confidence_threshold,
        "citation_coverage_threshold": settings.generation_citation_coverage_threshold,
        "semantic_validation_enabled": settings.generation_semantic_validation_enabled,
        "semantic_support_threshold": settings.generation_semantic_support_threshold,
        "semantic_validation_fail_open": settings.generation_semantic_validation_fail_open,
    }


def load_eval_questions(path: str = EVAL_FILE) -> list[dict[str, Any]]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"评估集不存在: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def invoke_graph(
    question: str,
    top_k: int = 3,
    session_id: str | None = None,
) -> dict[str, Any]:
    request_id = str(uuid4())
    result = industrial_rag_app.invoke({
        "question": question,
        "request_id": request_id,
        "session_id": session_id or f"evaluation-{request_id}",
        "user": None,
        "memory_enabled": True,
        "memory_messages": [],
        "memory_metadata": {},
        "knowledge_graph_metadata": {},
        "retrieval_filters": None,
        "multimodal_query": None,
        "intent": "rag",
        "query_features": {},
        "rewritten_query": "",
        "contexts": [],
        "generation_contexts": [],
        "generation_context_metadata": {},
        "answer": "",
        "citations": [],
        "retrieval_metadata": {},
        "evidence_score": 0.0,
        "evidence_enough": False,
        "evidence_confidence": 0.0,
        "evidence_reasons": [],
        "missing_aspects": [],
        "abstain_reason": None,
        "answer_abstained": False,
        "draft_answer": "",
        "generation_retry_count": 0,
        "generation_repair_error": None,
        "answer_validation": {},
        "answer_validation_history": [],
        "answer_structure": {},
        "generation_quality_passed": False,
        "citation_pruned": False,
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

    actual_intent = normalize_intent_label(result.get("intent"))
    return actual_intent == normalize_intent_label(expected_intent)


def check_doc_type(result: dict[str, Any], expected_doc_type: str | None) -> bool:
    if expected_doc_type is None:
        return True

    citations = result.get("citations", [])

    expected = normalize_document_type(expected_doc_type)
    for citation in citations:
        if normalize_document_type(citation.get("doc_type")) == expected:
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


def evaluate_one(
    item: dict[str, Any],
    *,
    invoke_fn=invoke_graph,
) -> dict[str, Any]:
    question = item["question"]
    session_id = f"evaluation-{uuid4()}"

    start = time.time()
    result = invoke_fn(
        question=question,
        top_k=3,
        session_id=session_id,
    )

    memory_followup_ok: bool | None = None
    followup_result: dict[str, Any] | None = None
    followup_question = item.get("followup_question")
    if followup_question:
        followup_result = invoke_fn(
            question=str(followup_question),
            top_k=3,
            session_id=session_id,
        )
        memory_followup_ok = check_answer_keywords(
            result=followup_result,
            expected_keywords=item.get("expected_followup_keywords"),
        )

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

    checks = [intent_ok, doc_type_ok, source_ok]
    if memory_followup_ok is not None:
        checks.append(memory_followup_ok)
    answer = str(result.get("answer", ""))
    answerable = bool(item.get("answerable", True))
    expected_intent = normalize_intent_label(item.get("expected_intent"))
    must_cite = bool(
        item.get(
            "must_cite",
            answerable and expected_intent == "rag",
        )
    )
    should_abstain = bool(item.get("should_abstain", not answerable))
    answer_abstained = bool(result.get("answer_abstained", False))
    abstention_ok = answer_abstained == should_abstain
    checks.append(answer_keywords_ok if answerable else abstention_ok)
    validation = result.get("answer_validation") or {}
    citation_coverage = float(validation.get("citation_coverage") or 0.0)
    citation_contract_ok = (
        bool(
            validation.get(
                "citation_contract_passed",
                validation.get("passed"),
            )
        )
        if must_cite
        else True
    )
    semantic_support_checked = bool(
        validation.get("semantic_support_checked", False)
    )
    semantic_support_rate = float(
        validation.get("semantic_support_rate") or 0.0
    )
    semantic_support_ok = (
        (
            semantic_support_checked
            and not validation.get("semantic_validation_degraded", False)
            and semantic_support_rate
            >= settings.generation_semantic_support_threshold
        )
        if must_cite and settings.generation_semantic_validation_enabled
        else None
    )
    generation_retry_count = int(result.get("generation_retry_count") or 0)
    repair_triggered = generation_retry_count > 0
    repair_success = repair_triggered and bool(
        result.get("generation_quality_passed", False)
    )
    validation_history = result.get("answer_validation_history", [])
    initial_validation = (
        validation_history[0]
        if validation_history and isinstance(validation_history[0], dict)
        else validation
    )
    validation_action = initial_validation.get("recommended_action")
    if not validation_action:
        initial_reasons = set(initial_validation.get("failure_reasons", []))
        if repair_triggered:
            # Backward compatibility for reports created before the validator
            # started recording its first-pass routing decision.
            validation_action = "llm_repair"
        elif initial_validation.get("passed", False):
            validation_action = "finalize"
        elif initial_reasons:
            validation_action = "deterministic_prune"
        else:
            validation_action = "finalize"
    repair_avoided = (
        validation_action == "deterministic_prune" and not repair_triggered
    )
    forbidden_claims = [
        str(value) for value in item.get("forbidden_claims", []) if value
    ]
    forbidden_claims_ok = not any(
        claim.lower() in answer.lower() for claim in forbidden_claims
    )

    quality_checks = {
        "citation_contract_ok": citation_contract_ok,
        "abstention_ok": abstention_ok,
        "forbidden_claims_ok": forbidden_claims_ok,
        "answer_nonempty": bool(answer.strip()),
    }
    if semantic_support_ok is not None:
        quality_checks["semantic_support_ok"] = semantic_support_ok
    checks.extend(quality_checks.values())
    all_ok = all(checks)

    evaluated = {
        "id": item.get("id"),
        "question": question,
        "expected_intent": normalize_intent_label(item.get("expected_intent")),
        "actual_intent": result.get("intent"),
        "expected_keywords": item.get("expected_answer_keywords") or [],
        "expected_sources": (
            [item["expected_source_contains"]]
            if item.get("expected_source_contains")
            else []
        ),
        "intent_ok": intent_ok,
        "doc_type_ok": doc_type_ok,
        "source_ok": source_ok,
        "answer_keywords_ok": answer_keywords_ok,
        "memory_followup_ok": memory_followup_ok,
        "all_ok": all_ok,
        "category": item.get("category"),
        "answerable": answerable,
        "must_cite": must_cite,
        "should_abstain": should_abstain,
        "answer_abstained": answer_abstained,
        "abstention_ok": abstention_ok,
        "citation_contract_ok": citation_contract_ok,
        "citation_coverage": round(citation_coverage, 4),
        "semantic_support_checked": semantic_support_checked,
        "semantic_support_rate": (
            round(semantic_support_rate, 4)
            if semantic_support_checked
            else None
        ),
        "semantic_support_ok": semantic_support_ok,
        "semantic_validation_degraded": bool(
            validation.get("semantic_validation_degraded", False)
        ),
        "answer_validation": validation,
        "answer_validation_history": validation_history,
        "validation_action": validation_action,
        "generation_retry_count": generation_retry_count,
        "repair_triggered": repair_triggered,
        "repair_avoided": repair_avoided,
        "repair_success": repair_success,
        "citation_pruned": bool(result.get("citation_pruned", False)),
        "evidence_enough": result.get("evidence_enough"),
        "evidence_confidence": result.get("evidence_confidence"),
        "evidence_threshold": settings.evidence_confidence_threshold,
        "evidence_reasons": result.get("evidence_reasons", []),
        "missing_aspects": result.get("missing_aspects", []),
        "abstain_reason": result.get("abstain_reason"),
        "forbidden_claims_ok": forbidden_claims_ok,
        "quality_checks": quality_checks,
        "latency_seconds": latency,
        "latency_ms": round(latency * 1000, 2),
        "answer": answer,
        "answer_preview": answer[:300],
        "citations": summarize_citations(result.get("citations", [])),
        "followup_answer": (
            str(followup_result.get("answer", ""))
            if followup_result
            else None
        ),
    }
    evaluated.update(classify_generation_result(evaluated))
    return evaluated


def calculate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)

    if total == 0:
        return {}

    def rate(key: str) -> float:
        count = sum(1 for item in results if item.get(key))
        return round(count / total, 4)

    avg_latency = round(
        sum(float(item.get("latency_seconds") or 0.0) for item in results) / total,
        3
    )
    latency_values_ms = sorted(
        float(item.get("latency_ms") or 0.0)
        for item in results
        if item.get("latency_ms") is not None
    )

    def percentile(values: list[float], quantile: float) -> float:
        if not values:
            return 0.0
        rank = max(0, math.ceil(quantile * len(values)) - 1)
        return round(values[rank], 2)

    citation_items = [item for item in results if item.get("must_cite")]
    semantic_checked_items = [
        item for item in citation_items if item.get("semantic_support_checked")
    ]
    repair_items = [item for item in results if item.get("repair_triggered")]
    llm_repair_actions = [
        item for item in results if item.get("validation_action") == "llm_repair"
    ]
    deterministic_prune_actions = [
        item
        for item in results
        if item.get("validation_action") == "deterministic_prune"
    ]
    finalize_actions = [
        item for item in results if item.get("validation_action") == "finalize"
    ]
    no_repair_items = [
        item for item in results if not item.get("repair_triggered")
    ]

    def avg_item_latency_ms(items: list[dict[str, Any]]) -> float:
        values = [
            float(item.get("latency_ms") or 0.0)
            for item in items
            if item.get("latency_ms") is not None
        ]
        return round(sum(values) / len(values), 2) if values else 0.0
    answerable_items = [item for item in results if item.get("answerable", True)]
    answer_keyword_hit_rate = (
        round(
            sum(1 for item in answerable_items if item.get("answer_keywords_ok"))
            / len(answerable_items),
            4,
        )
        if answerable_items
        else 0.0
    )

    memory_results = [
        item for item in results
        if item.get("memory_followup_ok") is not None
    ]
    memory_followup_success_rate = (
        round(
            sum(
                1 for item in memory_results
                if item.get("memory_followup_ok")
            ) / len(memory_results),
            4,
        )
        if memory_results
        else 0.0
    )

    metrics = {
        "total": total,
        "overall_pass_rate": rate("all_ok"),
        "intent_accuracy": rate("intent_ok"),
        "doc_type_accuracy": rate("doc_type_ok"),
        "source_accuracy": rate("source_ok"),
        "source_hit_rate": rate("source_ok"),
        "answer_keyword_hit_rate": answer_keyword_hit_rate,
        "memory_followup_success_rate": memory_followup_success_rate,
        "avg_latency_seconds": avg_latency,
        "avg_latency_ms": round(avg_latency * 1000, 2),
        "p95_latency_ms": percentile(latency_values_ms, 0.95),
        "citation_validation_pass_rate": (
            round(
                sum(1 for item in citation_items if item.get("citation_contract_ok"))
                / len(citation_items),
                4,
            )
            if citation_items
            else 0.0
        ),
        "avg_citation_coverage": (
            round(
                sum(float(item.get("citation_coverage") or 0.0) for item in citation_items)
                / len(citation_items),
                4,
            )
            if citation_items
            else 0.0
        ),
        "semantic_validation_coverage_rate": (
            round(len(semantic_checked_items) / len(citation_items), 4)
            if citation_items
            else 0.0
        ),
        "semantic_support_pass_rate": (
            round(
                sum(
                    1
                    for item in semantic_checked_items
                    if item.get("semantic_support_ok")
                )
                / len(semantic_checked_items),
                4,
            )
            if semantic_checked_items
            else 0.0
        ),
        "avg_semantic_support_rate": (
            round(
                sum(float(item.get("semantic_support_rate") or 0.0) for item in semantic_checked_items)
                / len(semantic_checked_items),
                4,
            )
            if semantic_checked_items
            else 0.0
        ),
        "repair_trigger_rate": rate("repair_triggered"),
        "llm_repair_selection_rate": (
            round(len(llm_repair_actions) / total, 4) if total else 0.0
        ),
        "deterministic_prune_selection_rate": (
            round(len(deterministic_prune_actions) / total, 4)
            if total
            else 0.0
        ),
        "direct_finalize_selection_rate": (
            round(len(finalize_actions) / total, 4) if total else 0.0
        ),
        "repair_avoidance_rate": rate("repair_avoided"),
        "avg_latency_llm_repair_ms": avg_item_latency_ms(repair_items),
        "avg_latency_without_llm_repair_ms": avg_item_latency_ms(
            no_repair_items
        ),
        "deterministic_citation_pruning_rate": rate("citation_pruned"),
        "repair_success_rate": (
            round(
                sum(1 for item in repair_items if item.get("repair_success"))
                / len(repair_items),
                4,
            )
            if repair_items
            else 0.0
        ),
        "final_refusal_rate": rate("answer_abstained"),
        "abstention_accuracy": rate("abstention_ok"),
        "forbidden_claims_pass_rate": rate("forbidden_claims_ok"),
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
        "prompt_release": get_prompt_registry().release_metadata(),
        "evaluation_fingerprint": build_evaluation_fingerprint(),
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
