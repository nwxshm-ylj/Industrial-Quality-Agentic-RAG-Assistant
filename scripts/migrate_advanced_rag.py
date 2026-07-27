"""Apply additive storage changes for multimodal RAG without demo-data reset."""

from sqlalchemy import text

from app.db.session import engine


DDL = """
CREATE TABLE IF NOT EXISTS document_assets (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(100) NOT NULL,
    asset_id VARCHAR(180) UNIQUE NOT NULL,
    page_number INT,
    modality VARCHAR(50) NOT NULL,
    text TEXT,
    asset_path TEXT,
    mime_type VARCHAR(100),
    source VARCHAR(255),
    version VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_assets_doc_id
    ON document_assets (doc_id);
CREATE INDEX IF NOT EXISTS idx_document_assets_asset_id
    ON document_assets (asset_id);
"""


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text(DDL))
    print({"status": "success", "migration": "advanced_rag_v1"})


if __name__ == "__main__":
    main()
