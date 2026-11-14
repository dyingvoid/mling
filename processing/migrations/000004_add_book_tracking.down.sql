BEGIN;

DROP INDEX IF EXISTS ix_mling_documents_book_checksum;

ALTER TABLE mling_documents
    DROP CONSTRAINT IF EXISTS fk_mling_documents_book_checksum,
    DROP COLUMN IF EXISTS book_checksum;

DROP TABLE IF EXISTS mling_book_leases;
DROP TABLE IF EXISTS mling_books;

COMMIT;
