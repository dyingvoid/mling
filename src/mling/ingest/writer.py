from __future__ import annotations

import json
from collections.abc import Sequence

from langchain_core.documents import Document
from sqlalchemy import Engine, text

from mling.ingest.documents import PROMOTED_METADATA
from mling.ingest.errors import LeaseLostError
from mling.ingest.lease import Lease
from mling.ingest.models import BookRecord
from mling.ingest.sql import quote_identifier

_INSERT_BATCH_SIZE = 250


class BookWriter:
    def __init__(
        self,
        engine: Engine,
        *,
        documents_table: str,
        dimension: int,
        books_table: str = "mling_books",
        leases_table: str = "mling_book_leases",
    ) -> None:
        documents = quote_identifier(documents_table)
        books = quote_identifier(books_table)
        leases = quote_identifier(leases_table)

        self._engine = engine
        self._dimension = dimension
        self._verify_lease_sql = text(
            f"SELECT 1 FROM {leases} WHERE checksum = :checksum AND token = :token FOR UPDATE"
        )
        self._delete_documents_sql = text(
            f"DELETE FROM {documents} WHERE book_checksum = :checksum"
        )
        self._insert_document_sql = text(
            f"""
            INSERT INTO {documents} (
                langchain_id, content, embedding, book_name, page,
                book_checksum, langchain_metadata
            )
            VALUES (
                :langchain_id, :content, CAST(:embedding AS vector), :book_name, :page,
                :book_checksum, CAST(:metadata AS jsonb)
            )
            """
        )
        self._upsert_book_sql = text(
            f"""
            INSERT INTO {books} (
                checksum, name, source, size_bytes, page_count, chunk_count,
                embedding_model, chunk_size, chunk_overlap, metadata, ingested_at
            )
            VALUES (
                :checksum, :name, :source, :size_bytes, :page_count, :chunk_count,
                :embedding_model, :chunk_size, :chunk_overlap,
                CAST(:metadata AS jsonb), now()
            )
            ON CONFLICT (checksum) DO UPDATE
               SET name = EXCLUDED.name,
                   source = EXCLUDED.source,
                   size_bytes = EXCLUDED.size_bytes,
                   page_count = EXCLUDED.page_count,
                   chunk_count = EXCLUDED.chunk_count,
                   embedding_model = EXCLUDED.embedding_model,
                   chunk_size = EXCLUDED.chunk_size,
                   chunk_overlap = EXCLUDED.chunk_overlap,
                   metadata = EXCLUDED.metadata,
                   ingested_at = now()
            """
        )
        self._delete_lease_sql = text(
            f"DELETE FROM {leases} WHERE checksum = :checksum AND token = :token"
        )
        self._get_book_sql = text(
            f"""
            SELECT checksum, name, source, size_bytes, page_count, chunk_count,
                   embedding_model, chunk_size, chunk_overlap, metadata, ingested_at
              FROM {books}
             WHERE checksum = :checksum
            """
        )

    def get(self, checksum: str) -> BookRecord | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                self._get_book_sql, {"checksum": checksum}
            ).first()
        if row is None:
            return None
        return BookRecord(
            checksum=row.checksum,
            name=row.name,
            source=row.source,
            size_bytes=row.size_bytes,
            page_count=row.page_count,
            chunk_count=row.chunk_count,
            embedding_model=row.embedding_model,
            chunk_size=row.chunk_size,
            chunk_overlap=row.chunk_overlap,
            metadata=dict(row.metadata),
            ingested_at=row.ingested_at,
        )

    def commit(
        self,
        lease: Lease,
        record: BookRecord,
        documents: Sequence[Document],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if record.checksum != lease.checksum:
            raise ValueError("book record and lease checksums must match")
        if len(documents) != len(vectors):
            raise ValueError("documents and vectors must have the same length")
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"expected embedding dimension {self._dimension}, got {len(vector)}"
                )

        rows = [
            _document_row(document, vector)
            for document, vector in zip(documents, vectors, strict=True)
        ]

        with self._engine.begin() as connection:
            owned = connection.execute(
                self._verify_lease_sql,
                {"checksum": lease.checksum, "token": lease.token},
            ).first()
            if owned is None:
                raise LeaseLostError(lease.checksum)

            connection.execute(
                self._upsert_book_sql,
                {
                    "checksum": record.checksum,
                    "name": record.name,
                    "source": record.source,
                    "size_bytes": record.size_bytes,
                    "page_count": record.page_count,
                    "chunk_count": record.chunk_count,
                    "embedding_model": record.embedding_model,
                    "chunk_size": record.chunk_size,
                    "chunk_overlap": record.chunk_overlap,
                    "metadata": json.dumps(record.metadata, ensure_ascii=False),
                },
            )
            connection.execute(
                self._delete_documents_sql, {"checksum": record.checksum}
            )
            for start in range(0, len(rows), _INSERT_BATCH_SIZE):
                connection.execute(
                    self._insert_document_sql,
                    rows[start : start + _INSERT_BATCH_SIZE],
                )
            connection.execute(
                self._delete_lease_sql,
                {"checksum": lease.checksum, "token": lease.token},
            )


def _document_row(
    document: Document, vector: Sequence[float]
) -> dict[str, object]:
    extra = {
        key: value
        for key, value in document.metadata.items()
        if key not in PROMOTED_METADATA
    }
    return {
        "langchain_id": document.id,
        "content": document.page_content,
        "embedding": str([float(value) for value in vector]),
        "book_name": document.metadata.get("book_name"),
        "page": document.metadata.get("page"),
        "book_checksum": document.metadata.get("book_checksum"),
        "metadata": json.dumps(extra, ensure_ascii=False),
    }
