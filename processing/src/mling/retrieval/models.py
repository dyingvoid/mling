from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    rank: int
    book_name: str
    page: int | None
    distance: float
    content: str
