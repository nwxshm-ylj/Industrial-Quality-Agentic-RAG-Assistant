from app.graph.nodes.evidence_judge_node import (
    evidence_judge_node,
    route_after_evidence_judge,
)


def main() -> None:
    strong = evidence_judge_node(
        {
            "question": "轮毂识别异常的原因和排查步骤是什么？",
            "rewritten_query": "轮毂识别异常 原因 排查步骤",
            "contexts": [
                {
                    "chunk_id": "wheel-1",
                    "text": "轮毂识别异常原因包括摄像头污染。排查时先检查镜头清洁度。",
                    "rerank_score": 0.92,
                    "final_score_type": "rerank_score",
                    "score": 0.92,
                },
                {
                    "chunk_id": "wheel-2",
                    "text": "检查光源角度并确认相机安装位置。",
                    "rerank_score": 0.80,
                    "final_score_type": "rerank_score",
                    "score": 0.80,
                },
            ],
            "retrieval_metadata": {"degraded": False},
            "retry_count": 0,
        }
    )
    assert strong["evidence_enough"] is True
    assert strong["evidence_confidence"] >= 0.55
    assert strong["missing_aspects"] == []
    assert route_after_evidence_judge(strong) == "generate"

    incomplete_coverage = evidence_judge_node(
        {
            "question": "某车型转向系统紧固扭矩阈值是多少？",
            "rewritten_query": "某车型 转向系统 紧固扭矩 阈值",
            "contexts": [
                {
                    "chunk_id": "parameter-1",
                    "text": "维修工艺文件记录了相关紧固参数。",
                    "rerank_score": 0.98,
                    "final_score_type": "rerank_score",
                    "score": 0.98,
                },
                {
                    "chunk_id": "parameter-2",
                    "text": "装配记录显示该项目需要复核。",
                    "rerank_score": 0.90,
                    "final_score_type": "rerank_score",
                    "score": 0.90,
                },
            ],
            "retrieval_metadata": {"degraded": False},
            "retry_count": 0,
        }
    )
    assert incomplete_coverage["evidence_confidence"] >= 0.55
    assert incomplete_coverage["evidence_enough"] is True
    assert incomplete_coverage["missing_aspects"] == []
    assert (
        incomplete_coverage["retrieval_metadata"]["requires_complete_evidence"]
        is True
    )
    assert (
        incomplete_coverage["retrieval_metadata"]["evidence_query_coverage"]
        is None
    )
    assert incomplete_coverage["retrieval_metadata"]["lexical_coverage_gate_enabled"] is False
    assert (
        incomplete_coverage["retrieval_metadata"]["evidence_decision_reason"]
        == "sufficient"
    )
    assert incomplete_coverage["abstain_reason"] is None

    ordinary_medium = evidence_judge_node(
        {
            "question": "装配异常如何处理？",
            "rewritten_query": "装配异常 处理",
            "contexts": [
                {
                    "chunk_id": "ordinary-medium",
                    "text": "装配异常时可先记录现场现象。",
                    "rerank_score": 0.40,
                    "final_score_type": "rerank_score",
                }
            ],
            "retrieval_metadata": {"degraded": False},
            "retry_count": 0,
        }
    )
    assert ordinary_medium["evidence_confidence"] == 0.425
    assert ordinary_medium["retrieval_metadata"]["evidence_level"] == "MEDIUM"
    assert ordinary_medium["retrieval_metadata"]["partial_answer_allowed"] is True
    assert ordinary_medium["evidence_enough"] is True

    strict_medium = evidence_judge_node(
        {
            "question": "安全扭矩阈值是多少？",
            "rewritten_query": "安全 扭矩 阈值",
            "contexts": [
                {
                    "chunk_id": "strict-medium",
                    "text": "装配记录包含相关检查说明。",
                    "rerank_score": 0.40,
                    "final_score_type": "rerank_score",
                }
            ],
            "retrieval_metadata": {"degraded": False},
            "retry_count": 0,
        }
    )
    assert strict_medium["evidence_confidence"] == 0.425
    assert strict_medium["retrieval_metadata"]["requires_complete_evidence"] is True
    assert strict_medium["retrieval_metadata"]["evidence_level"] == "LOW"
    assert strict_medium["retrieval_metadata"]["partial_answer_allowed"] is False
    assert strict_medium["retrieval_metadata"]["evidence_decision_reason"] == (
        "complete_evidence_required"
    )
    assert strict_medium["evidence_enough"] is False

    weak = evidence_judge_node(
        {
            "question": "轮毂识别异常原因是什么？",
            "rewritten_query": "轮毂识别异常 原因",
            "contexts": [
                {
                    "chunk_id": "unrelated-1",
                    "text": "本章节介绍车身颜色编码。",
                    "rerank_score": 0.10,
                    "final_score_type": "rerank_score",
                    "score": 0.10,
                }
            ],
            "retrieval_metadata": {"degraded": False},
            "retry_count": 0,
        }
    )
    assert weak["evidence_enough"] is False
    assert "原因" in weak["missing_aspects"]
    assert weak["abstain_reason"]
    assert route_after_evidence_judge(weak) == "rewrite"

    weak["retry_count"] = 2
    assert route_after_evidence_judge(weak) == "generate"

    unavailable = evidence_judge_node(
        {
            "question": "某未上传车型的高压电池热失控阈值是多少？",
            "rewritten_query": "某未上传车型 高压电池 热失控 阈值",
            "contexts": [
                {
                    "chunk_id": "similar-but-not-authoritative",
                    "text": "其他车型包含电池检查要求和温度参数。",
                    "rerank_score": 0.95,
                    "final_score_type": "rerank_score",
                }
            ],
            "retrieval_metadata": {"degraded": False},
            "retry_count": 0,
        }
    )
    assert unavailable["evidence_enough"] is False
    assert "目标对象资料未入库" in unavailable["missing_aspects"]
    assert "尚未上传" in unavailable["abstain_reason"]
    print("Evidence Judge 2.0 test passed")


if __name__ == "__main__":
    main()
