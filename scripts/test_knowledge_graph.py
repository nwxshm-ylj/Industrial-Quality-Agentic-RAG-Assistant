from app.knowledge_graph.service import KnowledgeGraphService


class _FakeGraphBackend:
    def __init__(self) -> None:
        self.schema_ready = False
        self.cases = []
        self.tokens = []

    def ensure_schema(self):
        self.schema_ready = True

    def upsert_quality_case(self, case):
        self.cases.append(case)

    def search_paths(self, tokens, limit):
        self.tokens = tokens
        return [
            {
                "nodes": [
                    {"labels": ["Station"], "name": "ZP8"},
                    {"labels": ["QualityCase"], "name": "Case 1: camera"},
                    {"labels": ["RootCause"], "name": "camera exposure"},
                ],
                "relationships": ["HAS_CASE", "CAUSED_BY"],
            }
        ][:limit]

    def close(self):
        return None


def main() -> None:
    backend = _FakeGraphBackend()
    service = KnowledgeGraphService(backend)
    count = service.sync_quality_cases(
        [
            {
                "id": 1,
                "station": "ZP8",
                "defect_type": "wheel_misrecognition",
                "phenomenon": "wheel type mismatch",
                "root_cause": "camera exposure",
                "action": "recalibrate camera",
                "model_type": "MEB",
                "part_code": "WHEEL",
            }
        ]
    )
    assert count == 1 and backend.schema_ready
    result = service.search_cases("ZP8 wheel camera historical cases", limit=5)
    assert result["path_count"] == 1
    assert "ZP8" in result["context"]
    assert "HAS_CASE" in result["context"]
    assert "zp8" in backend.tokens
    print("Knowledge graph service tests passed with a fake backend")


if __name__ == "__main__":
    main()
