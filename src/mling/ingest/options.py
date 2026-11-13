from __future__ import annotations

from dataclasses import dataclass

from mling.bookparse import Options as ParseOptions
from mling.indexing.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE

DEFAULT_EMBED_BATCH_SIZE = 64


@dataclass(frozen=True, slots=True)
class IngestOptions:
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    embed_batch_size: int = DEFAULT_EMBED_BATCH_SIZE
    dehyphenate: bool = False
    keep_blank_pages: bool = True
    force: bool = False

    def parse_options(self) -> ParseOptions:
        return ParseOptions(
            dehyphenate=self.dehyphenate,
            keep_blank_pages=self.keep_blank_pages,
        )
