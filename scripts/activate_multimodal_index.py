import argparse

from app.core.config import settings
from app.multimodal.factory import get_multimodal_embedding_provider
from app.rag.search_backends.multimodal_qdrant_backend import (
    MultimodalQdrantSearchBackend,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and activate the isolated multimodal Qdrant index"
    )
    parser.add_argument(
        "--activate-alias",
        action="store_true",
        help="Atomically point the stable alias after dimension/count validation",
    )
    args = parser.parse_args()

    backend = MultimodalQdrantSearchBackend(
        get_multimodal_embedding_provider(),
        collection_name=settings.qdrant_multimodal_collection,
        collection_alias=settings.qdrant_multimodal_collection_alias,
    )
    backend.ensure_index()
    indexed_count = backend.count_indexed()
    alias_target = backend.get_alias_target()
    print(
        {
            "collection": backend.collection_name,
            "alias": backend.collection_alias,
            "alias_target": alias_target,
            "indexed_count": indexed_count,
            "dimension": backend.embedding_provider.dimension,
        }
    )
    if args.activate_alias:
        backend.activate_alias()
        print(
            {
                "status": "activated",
                "alias_target": backend.get_alias_target(),
            }
        )


if __name__ == "__main__":
    main()
