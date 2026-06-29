from app.graph.state import IndustrialRAGState


def evidence_judge_node(state: IndustrialRAGState) -> dict:
    contexts = state.get("contexts", [])
    retry_count = state.get("retry_count", 0)

    if not contexts:
        evidence_score = 0.0
        evidence_enough = False
    else:
        scores = [
            float(ctx.get("score", 0.0))
            for ctx in contexts
        ]

        max_score = max(scores)
        avg_score = sum(scores) / len(scores)

        evidence_score = max_score

        # 第一版先用简单规则判断
        # bge-small + Qdrant cosine 场景下，0.55 可以作为初始经验阈值
        evidence_enough = max_score >= 0.55

        print("=" * 80)
        print("evidence_judge_node")
        print("max_score:", max_score)
        print("avg_score:", avg_score)
        print("evidence_enough:", evidence_enough)
        print("=" * 80)

    if not evidence_enough:
        retry_count += 1

    return {
        "evidence_score": evidence_score,
        "evidence_enough": evidence_enough,
        "retry_count": retry_count
    }


def route_after_evidence_judge(state: IndustrialRAGState) -> str:
    evidence_enough = state.get("evidence_enough", False)
    retry_count = state.get("retry_count", 0)

    if evidence_enough:
        return "generate"

    if retry_count <= 1:
        return "rewrite"

    return "generate"