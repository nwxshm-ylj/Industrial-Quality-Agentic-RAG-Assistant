import re
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.observability.model_usage import invoke_observed_chat_model


class IndustrialSQLTool:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            max_tokens=1024,
        )

        self.allowed_tables = {
            "inspection_record",
            "equipment_alarm",
            "quality_cases",
        }

        self.blocked_keywords = {
            "delete",
            "update",
            "drop",
            "insert",
            "alter",
            "truncate",
            "create",
            "grant",
            "revoke",
        }

    def run(self, question: str) -> dict[str, Any]:
        """
        SQL Tool 主入口：
        1. 优先匹配手写 SQL 模板；
        2. 如果没有命中模板，再调用 LLM 生成 SQL；
        3. 对 SQL 做安全校验；
        4. 执行 SQL；
        5. 返回结构化结果。
        """
        template_sql = self.match_template_sql(question)

        if template_sql:
            sql = template_sql
        else:
            sql = self.generate_sql(question)

        safe_sql = self.validate_and_fix_sql(sql)
        rows = self.execute_sql(safe_sql)

        return {
            "question": question,
            "sql": safe_sql,
            "rows": rows,
            "row_count": len(rows),
        }

    def match_template_sql(self, question: str) -> str | None:
        """
        高频问题优先走模板 SQL，避免 LLM 生成不稳定。
        """
        q = question.lower()

        if "最近一周" in q and "zp8" in q and ("误识别" in q or "不一致" in q):
            return """
            SELECT COUNT(*) AS mismatch_count
            FROM inspection_record
            WHERE station = 'ZP8'
              AND is_match = false
              AND created_at >= NOW() - INTERVAL '7 days'
            LIMIT 100;
            """

        if "置信度低于0.7" in q or "confidence低于0.7" in q or "confidence < 0.7" in q:
            return """
            SELECT record_id, vin, station, item, ai_result, mes_result, confidence, created_at
            FROM inspection_record
            WHERE confidence < 0.7
            ORDER BY created_at DESC
            LIMIT 100;
            """

        if "哪个工位报警最多" in q or "报警最多" in q:
            return """
            SELECT station, COUNT(*) AS alarm_count
            FROM equipment_alarm
            GROUP BY station
            ORDER BY alarm_count DESC
            LIMIT 10;
            """

        if "最近30天" in q and "报警代码" in q:
            return """
            SELECT alarm_code, COUNT(*) AS alarm_count
            FROM equipment_alarm
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY alarm_code
            ORDER BY alarm_count DESC
            LIMIT 100;
            """

        if "最常见的缺陷类型" in q or "缺陷类型最多" in q:
            return """
            SELECT defect_type, COUNT(*) AS case_count
            FROM quality_cases
            GROUP BY defect_type
            ORDER BY case_count DESC
            LIMIT 100;
            """

        return None

    def generate_sql(self, question: str) -> str:
        """
        使用 LLM 根据用户问题生成 PostgreSQL 查询。
        """
        schema = """
你可以查询以下 PostgreSQL 表：

1. inspection_record
字段：
- record_id: 记录ID
- vin: 车辆VIN
- station: 工位，例如 ZP8、ZP7、ZP6
- item: 检测项目，例如 wheel、mirror、badge、glass、door_panel
- ai_result: AI识别结果
- mes_result: MES配置结果
- is_match: AI结果与MES结果是否一致，true/false
- confidence: AI识别置信度
- created_at: 记录时间

2. equipment_alarm
字段：
- alarm_id: 报警ID
- equipment_id: 设备编号
- station: 工位
- alarm_code: 报警代码，例如 TQ001、CAM001、OCR001
- alarm_level: 报警等级，LOW/MEDIUM/HIGH
- sensor_value: 传感器数值
- resolved_action: 处理措施
- created_at: 报警时间

3. quality_cases
字段：
- case_id: 案例ID
- station: 工位
- defect_type: 缺陷类型
- phenomenon: 现象
- root_cause: 根因
- action: 处理措施
- model_type: 车型平台
- part_code: 零件/对象代码
- created_at: 案例时间

业务术语映射：
- 误识别 / 不一致 / 配置不一致：查询 inspection_record 表中 is_match = false
- 置信度低：查询 inspection_record 表中 confidence < 0.7
- 报警最多：查询 equipment_alarm 表，按 station 或 alarm_code 分组统计
- 最近一周：created_at >= NOW() - INTERVAL '7 days'
- 最近30天：created_at >= NOW() - INTERVAL '30 days'
- 质量案例：查询 quality_cases 表
- AI视觉检测记录：查询 inspection_record 表
- 设备报警记录：查询 equipment_alarm 表
"""

        system_prompt = """
你是一个 PostgreSQL 查询生成助手。

任务：
根据用户问题生成一条安全的 SELECT SQL。

要求：
1. 只能生成 SELECT 语句。
2. 不能生成 DELETE、UPDATE、DROP、INSERT、ALTER、CREATE 等语句。
3. 只能查询给定的三张表。
4. 必须添加 LIMIT，最大 LIMIT 100。
5. 不要使用不存在的字段。
6. 只输出 SQL，不要解释，不要 Markdown。
7. 时间条件可以使用 NOW() - INTERVAL '7 days' 这类 PostgreSQL 语法。
"""

        user_prompt = f"""
数据库结构：
{schema}

用户问题：
{question}

请生成 PostgreSQL SQL：
"""

        response = invoke_observed_chat_model(
            self.llm,
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ],
            component="sql_generator",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
        )

        sql = str(response.content).strip()
        sql = self._clean_sql(sql)

        return sql

    def _clean_sql(self, sql: str) -> str:
        """
        清理 LLM 返回的 SQL：
        - 去除 Markdown 代码块；
        - 只保留第一条 SQL；
        - 保持结尾分号。
        """
        sql = sql.strip()

        sql = re.sub(r"```sql", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"```", "", sql)
        sql = sql.strip()

        if ";" in sql:
            sql = sql.split(";")[0] + ";"
        else:
            sql = sql + ";"

        return sql.strip()

    def validate_and_fix_sql(self, sql: str) -> str:
        """
        SQL 安全检查：
        1. 只允许 SELECT；
        2. 禁止危险关键字；
        3. 只允许访问白名单表；
        4. 必须有 LIMIT；
        5. LIMIT 最大 100。
        """
        sql_clean = sql.strip()
        sql_lower = sql_clean.lower()

        if not sql_lower.startswith("select"):
            raise ValueError(f"只允许执行 SELECT 查询，当前 SQL: {sql_clean}")

        for keyword in self.blocked_keywords:
            if re.search(rf"\b{keyword}\b", sql_lower):
                raise ValueError(f"SQL 包含禁止关键字: {keyword}")

        used_tables = self._extract_tables(sql_lower)

        if not used_tables:
            raise ValueError(f"未识别到查询表: {sql_clean}")

        invalid_tables = used_tables - self.allowed_tables

        if invalid_tables:
            raise ValueError(f"SQL 查询了不允许的表: {invalid_tables}")

        if "limit" not in sql_lower:
            sql_clean = sql_clean.rstrip(";") + " LIMIT 100;"

        sql_clean = self._cap_limit(sql_clean)

        return sql_clean

    def _extract_tables(self, sql_lower: str) -> set[str]:
        """
        从 SQL 中提取 FROM / JOIN 后面的表名。
        注意：这里必须使用 \s，而不是 \\s。
        """
        tables = set()

        patterns = [
            r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sql_lower)
            tables.update(matches)

        return tables

    def _cap_limit(self, sql: str) -> str:
        """
        限制 LIMIT 最大为 100。
        """
        pattern = r"\blimit\s+(\d+)\b"

        match = re.search(pattern, sql, flags=re.IGNORECASE)

        if not match:
            return sql

        limit_value = int(match.group(1))

        if limit_value <= 100:
            return sql

        return re.sub(
            pattern,
            "LIMIT 100",
            sql,
            flags=re.IGNORECASE,
        )

    def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        """
        执行 SQL 并返回 list[dict]。
        """
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.mappings().all()

        return [dict(row) for row in rows]

    def format_sql_result_as_context(self, sql_result: dict[str, Any]) -> dict:
        """
        将 SQL 查询结果转成 RAG context 格式，
        方便后续 generate_node 复用 AnswerGenerator。
        """
        rows = sql_result.get("rows", [])
        sql = sql_result.get("sql", "")
        row_count = sql_result.get("row_count", 0)

        if not rows:
            text_content = f"""
SQL查询语句：
{sql}

查询结果：
未查询到相关记录。
"""
        else:
            preview_rows = rows[:10]
            row_lines = []

            for idx, row in enumerate(preview_rows, start=1):
                row_lines.append(f"{idx}. {row}")

            text_content = f"""
SQL查询语句：
{sql}

查询结果数量：
{row_count}

前10条结果：
{chr(10).join(row_lines)}
"""

        return {
            "text": text_content.strip(),
            "source": "PostgreSQL",
            "doc_type": "SQL_RESULT",
            "chunk_id": "sql_query_result",
            "score": 1.0,
        }
