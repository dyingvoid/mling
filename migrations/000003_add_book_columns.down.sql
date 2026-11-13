BEGIN;

DROP INDEX IF EXISTS ix_mling_documents_book_name_page;

ALTER TABLE mling_documents
    DROP COLUMN IF EXISTS page,
    DROP COLUMN IF EXISTS book_name;

COMMIT;
