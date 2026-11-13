BEGIN;

ALTER TABLE mling_documents
    ADD COLUMN IF NOT EXISTS book_name TEXT,
    ADD COLUMN IF NOT EXISTS page INTEGER;

CREATE INDEX IF NOT EXISTS ix_mling_documents_book_name_page
    ON mling_documents (book_name, page);

COMMIT;
