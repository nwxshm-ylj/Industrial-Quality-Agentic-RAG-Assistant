from app.knowledge_graph.service import KnowledgeGraphService


class _FakeGraphBackend:
    def __init__(self) -> None:
        self.schema_ready = False

    def ensure_schema(self):
        self.schema_ready = True

    def upsert_document_chunks(self, document, chunks):
        self.document = document
        self.chunks = chunks

    def delete_document(self, doc_id):
        self.deleted_doc_id = doc_id

    def search_traceability(self, entity_keys, limit):
        self.entity_keys = entity_keys
        return [
            {
                "nodes": [
                    {"labels": ["QualityEntity"], "name": "torque"},
                    {"labels": ["DocumentChunk"], "name": "doc-1-c1"},
                    {"labels": ["Document"], "name": "lesson.pptx"},
                ],
                "relationships": ["MENTIONS", "HAS_CHUNK"],
            }
        ][:limit]

    def close(self):
        return None


def main() -> None:
    backend = _FakeGraphBackend()
    service = KnowledgeGraphService(backend)
    chunk = {
        "text": "FDS torque evidence",
        "metadata": {
            "chunk_id": "doc-1-c1",
            "quality_entities": {
                "process_parameters": [
                    {"canonical_key": "torque", "name": "torque"}
                ]
            },
        },
    }
    assert service.sync_document(
        {
            "doc_id": "doc-1",
            "filename": "lesson.pptx",
            "doc_type": "LESSON_LEARNED",
            "version": "v1",
        },
        [chunk],
    ) == 1
    assert backend.schema_ready
    trace_result = service.search_traceability(
        "FDS torque issue",
        entities={
            "process_parameters": [
                {"canonical_key": "torque", "name": "torque"}
            ]
        },
        limit=5,
    )
    assert trace_result["path_count"] == 1
    assert backend.entity_keys == ["torque"]
    service.delete_document("doc-1")
    assert backend.deleted_doc_id == "doc-1"
    print("Knowledge graph service tests passed with a fake backend")


if __name__ == "__main__":
    main()
