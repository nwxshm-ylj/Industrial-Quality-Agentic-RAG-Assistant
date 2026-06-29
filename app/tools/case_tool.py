from typing import Any

from sqlalchemy import text

from app.db.session import engine


class IndustrialCaseTool:
    """
    历史质量案例检索工具。

    第一版基于 PostgreSQL 的 quality_cases 表做关键词检索。
    后续可以升级为：
    1. case 向量化检索；
    2. BM25 + SQL 过滤；
    3. case_retriever + reranker；
    4. 与文档 RAG 融合。
    """

    def search_cases(self, question: str, limit: int = 5) -> dict[str, Any]:
        defect_type = self._infer_defect_type(question)
        station = self._infer_station(question)

        rows = self._query_cases(
            defect_type=defect_type,
            station=station,
            limit=limit,
        )

        return {
            "question": question,
            "defect_type": defect_type,
            "station": station,
            "rows": rows,
            "row_count": len(rows),
        }

    def _infer_defect_type(self, question: str) -> str | None:
        q = question.lower()

        if "轮毂" in q or "wheel" in q or "误识别" in q:
            return "wheel_misrecognition"

        if "ocr" in q or "vin" in q or "合格证" in q:
            return "ocr_vin_failure"

        if "扭矩" in q or "拧紧" in q or "torque" in q:
            return "torque_alarm"

        if "配置" in q or "不一致" in q or "mes" in q:
            return "config_mismatch"

        return None

    def _infer_station(self, question: str) -> str | None:
        q = question.upper()

        known_stations = [
            "ZP8",
            "ZP7",
            "ZP6",
            "TORQUE01",
            "OCR01",
        ]

        for station in known_stations:
            if station in q:
                return station

        return None

    def _query_cases(
        self,
        defect_type: str | None,
        station: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        conditions = []
        params = {
            "limit": limit
        }

        if defect_type:
            conditions.append("defect_type = :defect_type")
            params["defect_type"] = defect_type

        if station:
            conditions.append("station = :station")
            params["station"] = station

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""
        SELECT
            case_id,
            station,
            defect_type,
            phenomenon,
            root_cause,
            action,
            model_type,
            part_code,
            created_at
        FROM quality_cases
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit
        """

        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.mappings().all()

        return [dict(row) for row in rows]

    def format_cases_as_context(self, case_result: dict[str, Any]) -> dict:
        rows = case_result.get("rows", [])
        row_count = case_result.get("row_count", 0)
        defect_type = case_result.get("defect_type")
        station = case_result.get("station")

        if not rows:
            text_content = f"""
历史案例检索结果：
未查询到匹配的历史案例。

检索条件：
- defect_type: {defect_type}
- station: {station}
"""
        else:
            case_lines = []

            for idx, row in enumerate(rows, start=1):
                case_lines.append(
                    f"""
案例 {idx}
- case_id: {row.get("case_id")}
- 工位: {row.get("station")}
- 缺陷类型: {row.get("defect_type")}
- 现象: {row.get("phenomenon")}
- 根因: {row.get("root_cause")}
- 措施: {row.get("action")}
- 车型平台: {row.get("model_type")}
- 对象代码: {row.get("part_code")}
- 时间: {row.get("created_at")}
"""
                )

            text_content = f"""
历史案例检索结果：

检索条件：
- defect_type: {defect_type}
- station: {station}

匹配案例数量：
{row_count}

案例详情：
{chr(10).join(case_lines)}
"""

        return {
            "text": text_content.strip(),
            "source": "PostgreSQL.quality_cases",
            "doc_type": "CASE_RESULT",
            "chunk_id": "case_search_result",
            "score": 1.0,
        }