from __future__ import annotations

import hashlib

from langchain_core.documents import Document

from mling.chunking import build_text_splitter
from mling.domain import Book
from mling.ingest.options import IngestOptions
from mling.schema import DOCUMENT_METADATA_COLUMNS

PROMOTED_METADATA = DOCUMENT_METADATA_COLUMNS


def book_to_documents(
    book: Book,
    *,
    checksum: str,
    name: str,
    options: IngestOptions,
) -> list[Document]:
    splitter = build_text_splitter(options.chunk_size, options.chunk_overlap)
    documents: list[Document] = []
    chunk_index = 0

    for page in book.pages:
        if not page.text.strip():
            continue
        for page_chunk_index, raw_chunk in enumerate(splitter.split_text(page.text)):
            content = raw_chunk.strip()
            if not content:
                continue
            metadata = {
                "book_name": name,
                "page": page.number,
                "book_checksum": checksum,
                "source": book.source,
                "format": book.format,
                "chunk_index": chunk_index,
                "page_chunk_index": page_chunk_index,
            }
            documents.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                    id=chunk_id(checksum, page.number, page_chunk_index),
                )
            )
            chunk_index += 1

    return documents


def chunk_id(checksum: str, page_number: int, page_chunk_index: int) -> str:
    key = f"{checksum}:{page_number}:{page_chunk_index}".encode()
    return hashlib.sha256(key).hexdigest()
