from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BookRecord:
    checksum: str
    name: str
    source: str
    size_bytes: int
    page_count: int
    chunk_count: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    metadata: dict[str, str]
    ingested_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    checksum: str
    name: str
    source: str
    page_count: int
    chunk_count: int
    skipped: bool = False
