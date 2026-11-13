BEGIN;

CREATE TABLE IF NOT EXISTS mling_documents (
    langchain_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    langchain_metadata JSONB
);

CREATE INDEX IF NOT EXISTS ix_mling_documents_embedding_cosine
    ON mling_documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMIT;
