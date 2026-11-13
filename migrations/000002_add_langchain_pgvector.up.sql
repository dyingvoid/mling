CREATE TABLE IF NOT EXISTS langchain_pg_collection (
    uuid uuid PRIMARY KEY,
    name varchar NOT NULL UNIQUE,
    cmetadata json
);

CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
    id varchar PRIMARY KEY,
    collection_id uuid REFERENCES langchain_pg_collection (uuid) ON DELETE CASCADE,
    embedding vector(384),
    document varchar,
    cmetadata jsonb
);

CREATE INDEX IF NOT EXISTS ix_langchain_pg_embedding_collection_id
    ON langchain_pg_embedding (collection_id);

CREATE INDEX IF NOT EXISTS ix_cmetadata_gin
    ON langchain_pg_embedding
    USING gin (cmetadata jsonb_path_ops);

CREATE INDEX IF NOT EXISTS ix_langchain_pg_embedding_embedding_cosine
    ON langchain_pg_embedding
    USING hnsw (embedding vector_cosine_ops);
