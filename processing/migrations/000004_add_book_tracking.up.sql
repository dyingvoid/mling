BEGIN;

CREATE TABLE IF NOT EXISTS mling_books (
    checksum TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    page_count INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    chunk_size INTEGER NOT NULL,
    chunk_overlap INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mling_book_leases (
    checksum TEXT PRIMARY KEY,
    token UUID NOT NULL,
    owner TEXT NOT NULL,
    source TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mling_book_leases_expires_at
    ON mling_book_leases (expires_at);

ALTER TABLE mling_documents
    ADD COLUMN IF NOT EXISTS book_checksum TEXT;

ALTER TABLE mling_documents
    ADD CONSTRAINT fk_mling_documents_book_checksum
    FOREIGN KEY (book_checksum)
    REFERENCES mling_books (checksum)
    ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS ix_mling_documents_book_checksum
    ON mling_documents (book_checksum);

COMMIT;
