from app.graph.query_features import classify_task_mode, extract_query_features
from app.rag.retrieval_filters import (
    RetrievalFilter,
    merge_retrieval_filter_mappings,
)
from app.traceability.entity_linker import QualityEntityLinker


def main() -> None:
    assert classify_task_mode("表面压印") == "knowledge_lookup"
    assert classify_task_mode("表面压印是什么") == "knowledge_lookup"
    assert classify_task_mode("表面压印如何返工") == "procedure_lookup"
    assert classify_task_mode("表面压印有哪些案例") == "case_search"
    assert classify_task_mode("5Q0810426A表面压印的原因") == "cause_trace"
    assert classify_task_mode("Tiguan车型的缺陷有哪些") == "case_search"
    assert classify_task_mode("Lavida售后缺陷") == "case_search"
    assert classify_task_mode("Lavida 的售后有哪些") == "case_search"
    assert classify_task_mode("车门问题有哪些") == "case_search"

    knowledge = extract_query_features("表面压印", "rag")
    assert knowledge["task_mode"] == "knowledge_lookup"
    assert knowledge["traceability_required"] is False
    assert knowledge["inferred_filters"]["failure_modes"] == [
        "surface_impression"
    ]

    tiguan = extract_query_features("Tiguan车型的缺陷有哪些", "rag")
    assert tiguan["task_mode"] == "case_search"
    assert tiguan["traceability_required"] is True
    assert tiguan["case_anchors"] == ["Tiguan"]
    assert tiguan["inferred_filters"]["vehicle_models"] == ["tiguan"]

    lavida = extract_query_features("Lavida售后缺陷", "rag")
    assert lavida["case_anchors"] == ["Lavida"]
    assert lavida["inferred_filters"]["vehicle_models"] == ["lavida"]

    anchored_cause = extract_query_features(
        "5Q0810426A表面压印的原因",
        "rag",
    )
    assert anchored_cause["task_mode"] == "cause_trace"
    assert anchored_cause["case_anchors"] == ["5Q0810426A"]
    assert anchored_cause["requires_case_anchor"] is False

    broad_cause = extract_query_features("表面压印的原因", "rag")
    assert broad_cause["requires_case_anchor"] is True

    door = QualityEntityLinker().link("车门问题有哪些")
    assert door["components"][0]["canonical_key"] == "door"

    retrieval_filter = RetrievalFilter.from_mapping(
        {
            "vehicle_models": ["tiguan"],
            "components": ["door"],
            "failure_modes": ["surface_impression"],
        }
    )
    assert retrieval_filter is not None
    assert retrieval_filter.as_dict() == {
        "vehicle_models": ["tiguan"],
        "components": ["door"],
        "failure_modes": ["surface_impression"],
    }
    assert merge_retrieval_filter_mappings(
        {"vehicle_models": ["caller-value"]},
        {"vehicle_models": ["tiguan"], "components": ["door"]},
    ) == {
        "vehicle_models": ["caller-value"],
        "components": ["door"],
    }
    print("Query task mode and inferred entity filter tests passed")


if __name__ == "__main__":
    main()
