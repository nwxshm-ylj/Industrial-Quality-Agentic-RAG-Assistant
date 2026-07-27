from sqlalchemy import text

from app.db.session import engine
from app.knowledge_graph.service import get_knowledge_graph_service


def main() -> None:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT case_id AS id, station, defect_type, phenomenon, root_cause,
                       action, model_type, part_code
                FROM quality_cases
                ORDER BY id
            """)
        ).mappings().all()
    cases = [dict(row) for row in rows]
    if not cases:
        print("No quality_cases rows found; graph sync skipped")
        return
    count = get_knowledge_graph_service().sync_quality_cases(cases)
    print({"status": "success", "synced_quality_cases": count})


if __name__ == "__main__":
    main()
