from app.rag.search_backends.base import (
    KeywordSearchBackend,
    VectorSearchBackend,
)


def activate_validated_vector_alias(
    vector_backend: VectorSearchBackend,
    keyword_backend: KeywordSearchBackend,
) -> dict:
    """Switch the vector alias only when both online indexes are complete."""

    vector_count = vector_backend.count_indexed()
    keyword_count = keyword_backend.count_indexed()
    if vector_count <= 0:
        raise RuntimeError("Cannot activate alias for an empty vector index")
    if vector_count != keyword_count:
        raise RuntimeError(
            "Cannot activate alias because online index counts differ: "
            f"qdrant={vector_count}, opensearch={keyword_count}"
        )

    activate_alias = getattr(vector_backend, "activate_alias", None)
    if not callable(activate_alias):
        raise RuntimeError("Configured vector backend does not support aliases")
    activate_alias()
    return {
        "vector_count": vector_count,
        "keyword_count": keyword_count,
        "alias_activated": True,
    }
