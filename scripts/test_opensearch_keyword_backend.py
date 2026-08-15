from app.rag.search_backends.opensearch_backend import OpenSearchKeywordBackend
from app.rag.retrieval_filters import RetrievalFilter


class _Indices:
    def __init__(self) -> None:
        self.created = {}
        self.mapping_updates = []

    def exists(self, *, index):
        return index in self.created

    def create(self, *, index, body):
        self.created[index] = body

    def put_mapping(self, *, index, body):
        self.mapping_updates.append((index, body))


class _FakeOpenSearchClient:
    def __init__(self) -> None:
        self.indices = _Indices()
        self.deleted = []
        self.updated = []
        self.searches = []
        self.indexed_count = 1

    def delete_by_query(self, **kwargs):
        self.deleted.append(kwargs)

    def search(self, **kwargs):
        self.searches.append(kwargs)
        return {
            "hits": {
                "hits": [
                    {
                        "_score": 4.2,
                        "_source": {
                            "doc_id": "d1",
                            "chunk_id": "d1_0",
                            "chunk_index": 0,
                            "text": "轮毂识别异常",
                            "source": "quality.txt",
                            "doc_type": "QUALITY",
                            "page_number": 3,
                            "parser_version": "deepdoc-layout-v1",
                            "chunk_strategy": "layout-token-v2",
                        },
                    }
                ]
            }
        }

    def update_by_query(self, **kwargs):
        self.updated.append(kwargs)

    def count(self, **kwargs):
        return {"count": self.indexed_count}

    def ping(self):
        return True


def main() -> None:
    client = _FakeOpenSearchClient()
    bulk_calls = []

    def fake_bulk(client_arg, actions, **kwargs):
        bulk_calls.append((client_arg, actions, kwargs))
        return len(actions), []

    backend = OpenSearchKeywordBackend(
        index_name="industrial_docs_keyword_v1",
        client=client,
        bulk_executor=fake_bulk,
    )
    chunks = [
        {
            "text": "轮毂识别异常",
            "metadata": {
                "chunk_id": "d1_0",
                "chunk_index": 0,
                "source": "quality.txt",
                "doc_type": "QUALITY",
                "version": "v1",
                "section_type": "table",
                "heading_path": "故障诊断 > 轮毂识别异常",
                "page_number": 3,
                "page_start": 3,
                "page_end": 4,
                "parser_version": "deepdoc-layout-v1",
                "chunk_strategy": "layout-token-v2",
            },
        }
    ]

    backend.upsert_document_chunks("d1", chunks)
    assert "industrial_docs_keyword_v1" in client.indices.created
    mapping = client.indices.created[backend.index_name]
    assert mapping["mappings"]["properties"]["doc_id"]["type"] == "keyword"
    assert mapping["mappings"]["properties"]["page_number"]["type"] == "integer"
    assert mapping["settings"]["index"]["max_ngram_diff"] == 2
    assert bulk_calls[0][1][0]["_id"] == "d1_0"
    indexed_source = bulk_calls[0][1][0]["_source"]
    assert indexed_source["page_number"] == 3
    assert indexed_source["parser_version"] == "deepdoc-layout-v1"
    assert bulk_calls[0][2]["refresh"] == "wait_for"

    results = backend.search("轮毂", top_k=5)
    assert results[0]["retrieval_source"] == "keyword"
    assert results[0]["page_number"] == 3
    assert results[0]["chunk_index"] == 0
    assert results[0]["parser_version"] == "deepdoc-layout-v1"
    assert backend.count_indexed() == 1
    assert client.searches[0]["body"]["query"]["bool"]["filter"] == [
        {"term": {"index_status": "indexed"}}
    ]
    backend.search(
        "quality",
        top_k=5,
        filters=RetrievalFilter(
            doc_ids=("d1",),
            doc_types=("QUALITY",),
            versions=("v1",),
            sources=("quality.txt",),
        ),
    )
    assert client.searches[1]["body"]["query"]["bool"]["filter"] == [
        {"term": {"index_status": "indexed"}},
        {"terms": {"doc_id": ["d1"]}},
        {"terms": {"doc_type": ["QUALITY"]}},
        {"terms": {"version": ["v1"]}},
        {"terms": {"source.keyword": ["quality.txt"]}},
    ]
    neighbors = backend.get_adjacent_chunks(
        [{"doc_id": "d1", "chunk_id": "d1_0", "chunk_index": 1}],
        window=1,
    )
    assert neighbors[0]["chunk_index"] == 0
    neighbor_bool = client.searches[2]["body"]["query"]["bool"]
    assert neighbor_bool["minimum_should_match"] == 1
    assert neighbor_bool["must_not"] == [{"terms": {"chunk_id": ["d1_0"]}}]

    backend.delete_by_doc_id("d1")
    delete_bool = client.deleted[0]["body"]["query"]["bool"]
    assert delete_bool["filter"] == [
        {"term": {"doc_id": "d1"}}
    ]
    assert delete_bool["must_not"] == []
    backend.delete_all_except_operation("migration-1")
    stale_cleanup = client.deleted[1]["body"]["query"]["bool"]
    assert stale_cleanup["must_not"] == [
        {"term": {"index_operation_id": "migration-1"}}
    ]
    backend.set_document_index_status(
        "d1",
        "indexed",
        index_operation_id="operation-1",
    )
    assert client.updated[0]["body"]["script"]["params"]["status"] == "indexed"
    assert backend.is_available() is True

    existing_backend = OpenSearchKeywordBackend(
        index_name="industrial_docs_keyword_v1",
        client=client,
        bulk_executor=fake_bulk,
    )
    existing_backend.ensure_index()
    assert client.indices.mapping_updates[0][0] == "industrial_docs_keyword_v1"
    assert (
        client.indices.mapping_updates[0][1]["properties"]["chunk_strategy"]["type"]
        == "keyword"
    )
    print("OpenSearch keyword backend tests passed without OpenSearch SDK/network")


if __name__ == "__main__":
    main()
