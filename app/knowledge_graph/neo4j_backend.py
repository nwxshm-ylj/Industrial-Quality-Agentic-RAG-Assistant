from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.knowledge_graph.base import KnowledgeGraphError


class Neo4jKnowledgeGraphBackend:
    def __init__(self, driver: Any, *, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT quality_case_id IF NOT EXISTS "
            "FOR (n:QualityCase) REQUIRE n.case_id IS UNIQUE",
            "CREATE CONSTRAINT station_name IF NOT EXISTS "
            "FOR (n:Station) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT defect_name IF NOT EXISTS "
            "FOR (n:Defect) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT part_name IF NOT EXISTS "
            "FOR (n:Part) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT model_name IF NOT EXISTS "
            "FOR (n:VehicleModel) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT cause_name IF NOT EXISTS "
            "FOR (n:RootCause) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT action_name IF NOT EXISTS "
            "FOR (n:CorrectiveAction) REQUIRE n.name IS UNIQUE",
        ]
        try:
            with self.driver.session(database=self.database) as session:
                for statement in statements:
                    session.run(statement).consume()
        except Exception as exc:
            raise KnowledgeGraphError(f"Neo4j schema setup failed: {exc}") from exc

    def upsert_quality_case(self, case: dict) -> None:
        required = {
            "id",
            "station",
            "defect_type",
            "root_cause",
            "action",
            "model_type",
            "part_code",
        }
        missing = sorted(required.difference(case))
        if missing:
            raise ValueError(f"quality case missing fields: {missing}")
        query = """
        MERGE (c:QualityCase {case_id: $case_id})
        SET c.name = $case_name, c.phenomenon = $phenomenon
        MERGE (s:Station {name: $station})
        MERGE (d:Defect {name: $defect_type})
        MERGE (p:Part {name: $part_code})
        MERGE (m:VehicleModel {name: $model_type})
        MERGE (r:RootCause {name: $root_cause})
        MERGE (a:CorrectiveAction {name: $action})
        MERGE (s)-[:HAS_CASE]->(c)
        MERGE (c)-[:HAS_DEFECT]->(d)
        MERGE (c)-[:AFFECTS_PART]->(p)
        MERGE (c)-[:APPLIES_TO]->(m)
        MERGE (c)-[:CAUSED_BY]->(r)
        MERGE (c)-[:RESOLVED_BY]->(a)
        """
        parameters = {
            "case_id": str(case["id"]),
            "case_name": f"Case {case['id']}: {case['defect_type']}",
            "phenomenon": case.get("phenomenon"),
            "station": str(case["station"]),
            "defect_type": str(case["defect_type"]),
            "part_code": str(case["part_code"]),
            "model_type": str(case["model_type"]),
            "root_cause": str(case["root_cause"]),
            "action": str(case["action"]),
        }
        try:
            with self.driver.session(database=self.database) as session:
                session.run(query, parameters).consume()
        except Exception as exc:
            raise KnowledgeGraphError(f"Neo4j case upsert failed: {exc}") from exc

    def search_paths(self, tokens: list[str], limit: int) -> list[dict]:
        if not tokens or limit <= 0:
            return []
        query = """
        MATCH (anchor)
        WHERE anchor.name IS NOT NULL
          AND any(token IN $tokens
                  WHERE toLower(toString(anchor.name)) CONTAINS token)
        MATCH path=(anchor)-[*0..2]-(related)
        WITH path LIMIT $limit
        RETURN
          [node IN nodes(path) | {
            labels: labels(node),
            name: coalesce(node.name, node.case_id),
            case_id: node.case_id,
            phenomenon: node.phenomenon
          }] AS nodes,
          [rel IN relationships(path) | type(rel)] AS relationships
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    query,
                    tokens=[token.lower() for token in tokens],
                    limit=limit,
                )
                return [dict(record) for record in result]
        except Exception as exc:
            raise KnowledgeGraphError(f"Neo4j graph search failed: {exc}") from exc

    def close(self) -> None:
        self.driver.close()


@lru_cache(maxsize=1)
def get_neo4j_backend() -> Neo4jKnowledgeGraphBackend:
    from neo4j import GraphDatabase

    from app.core.config import settings

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
        connection_timeout=settings.neo4j_connection_timeout_seconds,
        max_connection_pool_size=settings.neo4j_max_connection_pool_size,
    )
    return Neo4jKnowledgeGraphBackend(
        driver,
        database=settings.neo4j_database,
    )
