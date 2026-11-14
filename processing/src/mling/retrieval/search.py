from __future__ import annotations

from typing import Any

from mling.config import Settings
from mling.indexing.vector_store import EmbeddingStore
from mling.retrieval.models import RetrievalHit
from mling.retrieval.options import RetrievalOptions


def build_filter(options: RetrievalOptions) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = [{"book_name": options.book_name}]
    if options.from_page is not None:
        clauses.append({"page": {"$gte": options.from_page}})
    if options.to_page is not None:
        clauses.append({"page": {"$lte": options.to_page}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def retrieve(
    options: RetrievalOptions,
    *,
    settings: Settings | None = None,
    store: EmbeddingStore | None = None,
) -> list[RetrievalHit]:
    options.validate()
    owns_store = store is None
    store = store or EmbeddingStore.from_settings(settings or Settings.from_env())

    try:
        rows = store.search_with_score(
            options.query,
            k=options.limit,
            filter=build_filter(options),
        )
    finally:
        if owns_store:
            store.close()

    return [
        RetrievalHit(
            rank=rank,
            book_name=str(document.metadata.get("book_name", options.book_name)),
            page=document.metadata.get("page"),
            distance=float(distance),
            content=document.page_content,
        )
        for rank, (document, distance) in enumerate(rows, start=1)
    ]
